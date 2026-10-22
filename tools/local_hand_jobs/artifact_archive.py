"""Optional local consumer of completed evidence and the public Artifact Ledger API.

Linux, one trusted local user and one cooperative writer per store. Inputs are
retained authenticated tool results; their origin is the caller's responsibility.
No execution, remote calls, patch application or artifact code loading occurs.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import uuid
import zipfile

from local_hand.bounded_io import read_regular_file_bounded
from local_hand.protocol import LocalHandError
from .contract import JobError


MAX_BLOB = 64 * 1024 * 1024
MAX_RECOVERY_METADATA_BYTES = 1024 * 1024 * 1024
LIMITS = {"evidence.zip": MAX_BLOB, "evidence.manifest": 4 * 1024 * 1024,
          "evidence.seal": 65536, "status.json": 1024 * 1024, "source.json": 65536}
TYPE = {"namespace": "local-hand", "type_id": "completed-evidence", "type_version": "1"}


class ArchiveError(Exception):
    def __init__(self, code, message, commit_state="not_applicable"):
        super().__init__(message)
        self.code, self.commit_state = code, commit_state


def _fail(message, code="CONFLICT"):
    raise ArchiveError(code, message)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _fail("Duplicate JSON field")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                           parse_constant=lambda _: _fail("Non-finite JSON value"))
        if not isinstance(value, dict):
            _fail("Expected a JSON object")
        return value
    except (ValueError, UnicodeError, RecursionError):
        _fail("Invalid bounded UTF-8 JSON input")


def _digest(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail("Expected a lowercase SHA-256 digest", "INVALID_INPUT")
    return value


def _identity(value):
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,255}", value) is None:
        _fail("Expected an explicit stable identity", "INVALID_INPUT")
    return value


def _ledger_api():
    if sys.platform != "linux":
        _fail("Local artifact archives currently support Linux only", "UNSUPPORTED")
    try:
        import infra_artifact_ledger
    except ImportError:
        _fail("Install the verified infra-artifact-ledger wheel in this environment", "DEPENDENCY_MISSING")
    return infra_artifact_ledger


def _read(path, maximum):
    return read_regular_file_bounded(Path(path), maximum, "archive_input_unavailable")


def _task_name(producer, operation_id):
    # A private index key, never an Artifact or Version identity.
    return "task-" + _sha(_json([_identity(producer), _identity(operation_id)]))


def _task_scope(producer, operation_id):
    return "local-hand:archive:" + _task_name(producer, operation_id)


def _physical_database_identity(path):
    """Read the file and filesystem identities from the same no-follow handle."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid() or info.st_mode & 0o077):
            _fail("Ledger files must be private regular files")
        filesystem = os.fstatvfs(fd).f_fsid
        if type(filesystem) is not int or filesystem <= 0:
            _fail("A stable local filesystem identity is required", "UNSUPPORTED")
        return dict(device=info.st_dev, inode=info.st_ino, filesystem_id=filesystem)
    finally:
        os.close(fd)


def _filesystem_binding(path):
    from .evidence import _open_root
    marker = path.parent / "database-initialized"
    if not os.path.lexists(marker):
        return None
    with _open_root(marker, os.geteuid()):
        record = _decode(_read(marker / "format.json", 4096))
        if record.get("schema_version") == "lh-artifact-store-v3":
            binding = record.get("filesystem_binding")
        else:
            guard = marker / "filesystem-binding"
            if not os.path.lexists(guard):
                return None
            with _open_root(guard, os.geteuid()):
                binding = _decode(_read(guard / "identity.json", 4096))
    if (not isinstance(binding, dict)
            or set(binding) != {"schema_version", "database_identity", "filesystem_id", "checkpoint_sha256"}
            or binding["schema_version"] != "lh-artifact-filesystem-v1"
            or not isinstance(binding["database_identity"], dict)
            or set(binding["database_identity"]) != {"device", "inode"}
            or any(type(v) is not int or v < 0 for v in binding["database_identity"].values())
            or type(binding["filesystem_id"]) is not int or binding["filesystem_id"] <= 0
            or (binding["checkpoint_sha256"] is not None and
                (not isinstance(binding["checkpoint_sha256"], str) or
                 re.fullmatch(r"[0-9a-f]{64}", binding["checkpoint_sha256"]) is None))):
        _fail("Invalid archive filesystem binding", "INTEGRITY_FAILURE")
    return binding


def _database_identity(path):
    physical = _physical_database_identity(path)
    binding = _filesystem_binding(path)
    recovery = path.parent / "database-initialized" / _recovery_name(physical)
    if os.path.lexists(recovery):
        from .evidence import _open_root
        with _open_root(recovery, os.geteuid()):
            record = _decode(_read(recovery / "identity.json", 4096))
        _validate_recovery_binding(record)
        if (record["physical_identity"] != _persistent_identity(physical)
                or record["database_identity"] != _original_database_identity(path.parent)):
            _fail("Restored database binding differs from this archive", "INTEGRITY_FAILURE")
        return record["database_identity"]
    if binding is not None:
        if (physical["filesystem_id"] != binding["filesystem_id"]
                or physical["inode"] != binding["database_identity"]["inode"]):
            _fail("Ledger filesystem or inode changed; retain the original store")
        # Keep all original reservation bytes. Device numbers are only locators;
        # the persisted filesystem ID and inode now establish continuity.
        return binding["database_identity"]
    return {key: physical[key] for key in ("device", "inode")}


@contextmanager
def _locked_store(store, *, create=False, read_only=False):
    if sys.platform != "linux":
        _fail("Local artifact archives currently support Linux only", "UNSUPPORTED")
    import fcntl
    from .evidence import _open_root, _sync_directory_ancestry
    root = Path(store).absolute()
    with _open_root(root, os.geteuid(), create=create) as directory:
        if create and read_only:
            _fail("A read-only call cannot create an archive", "INVALID_INPUT")
        flags = (os.O_RDONLY if read_only else os.O_RDWR) | os.O_NOFOLLOW | os.O_NONBLOCK
        fd = os.open(".archive.lock", flags | (os.O_CREAT if create else 0), 0o600, dir_fd=directory)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid != os.geteuid() or info.st_mode & 0o077):
                _fail("Archive lock is not a private regular file")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                _fail("Another archive call holds this store; retry the same request later", "BUSY")
            if create:
                os.fsync(fd)
                _sync_directory_ancestry(root, os.geteuid())
            yield root
        finally:
            os.close(fd)


def _publish_files(parent, name, files):
    """Sync all files before publishing a new directory; retain failed staging."""
    from .evidence import _open_root, _publish_create_only
    with _open_root(parent, os.geteuid()) as parent_fd:
        staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=parent))
        for filename, raw in files.items():
            with (staging / filename).open("xb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        with _open_root(staging, os.geteuid()) as directory:
            os.fsync(directory)
        _publish_create_only(staging, parent / name)
        os.fsync(parent_fd)


def _status(raw, expected_sha256):
    if _sha(raw) != _digest(expected_sha256):
        _fail("Status differs from the caller's trusted digest")
    value = _decode(raw)
    if "structuredContent" in value:
        if value.get("isError") is not False:
            _fail("Tool result is not a confirmed successful response")
        value = value["structuredContent"]
    if (not isinstance(value, dict) or value.get("lifecycle") != "TERMINAL"
            or value.get("phase") != "EXITED" or value.get("outcome") != "SUCCEEDED"
            or value.get("evidence") != "SEALED"):
        _fail("Only completed SUCCEEDED / SEALED tasks are supported", "INVALID_INPUT")
    _identity(value.get("operation_id"))
    _digest(value.get("request_digest"))
    refs = value.get("seal_refs")
    if not isinstance(refs, list) or len(refs) != 1 or not isinstance(refs[0], dict):
        _fail("Exactly one trusted seal reference is required")
    _identity(refs[0].get("seal_id"))
    _digest(refs[0].get("seal_sha256"))
    return value


def _source(files, producer, status_sha256):
    from .evidence_client import verify_local_bundle
    status = _status(files["status.json"], status_sha256)
    seal = status["seal_refs"][0]
    manifest = verify_local_bundle(files["evidence.zip"], files["evidence.manifest"],
        files["evidence.seal"], operation_id=status["operation_id"], **seal)
    source = dict(schema_version="lh-artifact-source-v1", producer=_identity(producer),
                  operation_id=status["operation_id"], request_digest=status["request_digest"],
                  status_sha256=status_sha256, outcome=status["outcome"], **seal)
    names = [m["name"] for m in manifest["members"] if m["name"].endswith("/workspace-result.json")]
    if names:
        if len(names) != 1:
            _fail("Ambiguous workspace result in the sealed evidence")
        with zipfile.ZipFile(io.BytesIO(files["evidence.zip"])) as archive:
            if archive.getinfo(names[0]).file_size > 65536:
                _fail("Workspace result exceeds its byte budget", "LIMIT_EXCEEDED")
            result = _decode(archive.read(names[0]))
            if (result.get("schema_version") != "lh-workspace-edit-v1"
                    or result.get("scope") != "TASK_OWNED_COPY"
                    or result.get("original_modified") is not False
                    or any(result.get(key) is not True for key in ("read_back_verified",
                        "validation_succeeded", "edited_file_unchanged_by_validation"))):
                _fail("Workspace result does not describe a validated private edit")
            if (not isinstance(result.get("source_commit"), str)
                    or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", result["source_commit"]) is None
                    or any(not isinstance(result.get(key), str) or not result[key]
                           for key in ("source_ref", "relative_path", "validation_ref"))):
                _fail("Workspace source or validation identity is invalid")
            prefix = names[0].rsplit("/", 1)[0] + "/"
            for label in ("before", "after"):
                member = next((m for m in manifest["members"]
                               if m["name"] == prefix + "workspace-" + label + ".txt"), None)
                if member is None or member["sha256"] != result.get(label + "_sha256"):
                    _fail("Workspace before/after binding differs from the manifest")
            source["workspace"] = result
    return source


def _request_templates(binding):
    """Derive request ownership from the retained mapping, not request contents."""
    if binding.get("schema_version") not in ("lh-artifact-request-v1", "lh-artifact-request-v2"):
        _fail("Unsupported retained task mapping", "INTEGRITY_FAILURE")
    _identity(binding.get("producer"))
    _identity(binding.get("operation_id"))
    _digest(binding.get("status_sha256"))
    token = binding.get("token")
    if not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{32}", token) is None:
        _fail("Invalid retained archive identity")
    ids = {kind: kind + ":" + token for kind in ("artifact", "version", "root", "manifest")}
    base = dict(profile="bounded-local-v0.1", contract_version="0.1.0",
                idempotency_scope_ref=(_task_scope(binding["producer"], binding["operation_id"])
                    if binding["schema_version"] == "lh-artifact-request-v2"
                    else "local-hand:archive:" + token))
    create = dict(base, operation_kind="create_artifact", idempotency_key="create",
                  body={"artifact": dict(artifact_id=ids["artifact"],
                    namespace_ref="local-hand:completed-results", type_ref=TYPE)})
    source_ref = "local-hand:" + binding["producer"] + ":" + binding["operation_id"]
    if len(source_ref) > 512:
        _fail("Combined source identity exceeds the Ledger reference limit", "LIMIT_EXCEEDED")
    append = dict(base, operation_kind="append_version", idempotency_key="append",
        body=dict(version=dict(version_id=ids["version"], artifact_id=ids["artifact"],
            content_root_ref=ids["root"], parent_version_refs=[], external_source_refs=[source_ref],
            capture_refs=[], handling_policy_refs=[])))
    return ids, create, append


def _requests(binding, files):
    ids, create, append = _request_templates(binding)
    token = binding["token"]
    entries, blobs, payloads = [], [], {}
    for number, name in enumerate(sorted(LIMITS)):
        ref = "blob:" + token + ":" + str(number)
        entries.append(dict(entry_key=name, blob_ref=ref))
        blobs.append(dict(blob_ref=ref, digest=dict(algorithm="sha256", value=_sha(files[name])),
                          byte_length=len(files[name]), payload_availability="available"))
        payloads[ref] = files[name]
    append["body"].update(
        content_roots=[dict(content_root_ref=ids["root"], kind="manifest", manifest_ref=ids["manifest"])],
        manifests=[dict(manifest_ref=ids["manifest"], entries=entries,
                        digest=dict(algorithm="sha256", value=_sha(_json(dict(entries=entries)))))],
        blobs=blobs, provenance_links=[])
    return _json(create), _json(append), payloads


def _fingerprint(request):
    # Public bounded-local-v0.1 fingerprint algorithm; no private Ledger imports.
    return {"algorithm": "sha256", "value": _sha(_json({key: request[key] for key in
        ("contract_version", "idempotency_scope_ref", "operation_kind", "body")}))}


def _ensure_operation(ledger, raw, *, payloads=None, receipt_directory=None, require_existing=False,
                      verify_only=False):
    # Maintenance verification can inspect existing history but must neither
    # execute an absent operation nor publish a missing confirmation receipt.
    from .evidence import _open_root, _sync_directory_ancestry
    api = _ledger_api()
    request = _decode(raw)
    kind = request["operation_kind"]
    result_kind, id_field = ("artifact", "artifact_id") if kind == "create_artifact" else ("version", "version_id")
    expected = request["body"][result_kind]
    receipt = None
    receipt_path = receipt_directory / kind if receipt_directory is not None else None
    if receipt_path is not None and os.path.lexists(receipt_path):
        with _open_root(receipt_path, os.geteuid()):
            receipt = _decode(_read(receipt_path / "commit.json", 4096))
        if receipt.get("request_sha256") != _sha(raw):
            _fail("Retained commit receipt differs from the original request", "INTEGRITY_FAILURE")
    try:
        previous = ledger.get_operation(request["idempotency_scope_ref"], kind, request["idempotency_key"])
    except api.LedgerError as error:
        if error.code != "NOT_FOUND":
            raise
        if receipt is not None or require_existing or verify_only:
            _fail("Previously confirmed archive operation is missing; restore the original database",
                  "INTEGRITY_FAILURE")
        # Only an unconfirmed original request may be executed after NOT_FOUND.
        result = ledger.execute(raw, **({"payloads": payloads} if payloads is not None else {}))
    else:
        record = previous["idempotency_record"]
        if (any(record[key] != request[key] for key in
                ("idempotency_scope_ref", "operation_kind", "idempotency_key"))
                or record["request_fingerprint"] != _fingerprint(request)
                or record["result_ref"] != expected[id_field]
                or any(previous["result"].get(key) != value for key, value in expected.items())):
            _fail("Stored operation differs from the retained request", "IDEMPOTENCY_CONFLICT")
        # The public create/append API stamps the primary record and its
        # operation in the same transaction. Neither may contradict the other.
        if previous["result"].get("recorded_at") != record["recorded_at"]:
            _fail("Stored result timestamp differs from its original operation", "INTEGRITY_FAILURE")
        result = dict(status="COMMITTED", commit_state="committed", operation_kind=kind,
                      result_ref=record["result_ref"], recorded_at=record["recorded_at"], replayed=True)
    if (result.get("status") != "COMMITTED" or result.get("commit_state") != "committed"
            or result.get("result_ref") != expected[id_field]):
        raise ArchiveError("UNCONFIRMED", "Ledger response did not confirm the original request", "unknown")
    if receipt_path is not None:
        confirmed = dict(schema_version="lh-artifact-commit-v1", request_sha256=_sha(raw),
            result={key: result[key] for key in
                ("status", "commit_state", "operation_kind", "result_ref", "recorded_at")})
        if receipt is None:
            if not verify_only:
                _publish_files(receipt_directory, kind, {"commit.json": _json(confirmed)})
        else:
            if receipt != confirmed:
                _fail("Stored operation differs from its confirmed commit receipt", "INTEGRITY_FAILURE")
            # A previous publication can be visible despite a failed parent sync.
            if not verify_only:
                _sync_directory_ancestry(receipt_path, os.geteuid())
    return result


def _original_database_identity(root):
    from .evidence import _open_root
    marker = root / "database-initialized"
    identity = None
    if os.path.lexists(marker):
        with _open_root(marker, os.geteuid()):
            format_record = _decode(_read(marker / "format.json", 4096))
            if format_record.get("schema_version") in ("lh-artifact-store-v2", "lh-artifact-store-v3"):
                identity = format_record["database_identity"]
                if (not isinstance(identity, dict) or set(identity) != {"device", "inode"}
                        or any(type(value) is not int or value < 0 for value in identity.values())):
                    _fail("Invalid archive database identity")
            elif format_record == {"schema_version": "lh-artifact-store-v1"}:
                # Preserve the original format file. Legacy stores gain an
                # identity guard on their first archive/resume with this code.
                guard = marker / "database-identity"
                if os.path.lexists(guard):
                    with _open_root(guard, os.geteuid()):
                        identity = _decode(_read(guard / "identity.json", 1024))
            else:
                _fail("Unsupported archive store format", "UNSUPPORTED")
    if identity is not None and (not isinstance(identity, dict) or set(identity) != {"device", "inode"}
            or any(type(v) is not int or v < 0 for v in identity.values())):
        _fail("Invalid original database identity", "INTEGRITY_FAILURE")
    return identity


def _database(root, *, create=False):
    from .evidence import _open_root, _sync_directory_ancestry
    api = _ledger_api()
    path = root / "ledger.sqlite"
    for candidate in (path, *(Path(str(path) + s) for s in ("-journal", "-wal", "-shm"))):
        if os.path.lexists(candidate):
            info = candidate.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid != os.geteuid() or info.st_mode & 0o077):
                _fail("Ledger files must be private regular files")
    marker = root / "database-initialized"
    identity = _original_database_identity(root)
    if not os.path.lexists(path) and os.path.lexists(marker):
        _fail("Previously initialized Ledger is missing; retain requests and restore the original store")
    if identity is not None and identity != _database_identity(path):
        _fail("Ledger file identity changed; retain requests and restore the original database")
    ledger = api.initialize(path) if not os.path.lexists(path) and create else api.open(path)
    try:
        current_identity = _database_identity(path)
        if identity is not None and identity != current_identity:
            _fail("Ledger file identity changed while opening")
        if create and not os.path.lexists(marker):
            # No artifact write is allowed until this initialization fence is
            # durable. Losing a database later must never silently recreate it.
            physical = _physical_database_identity(path)
            _publish_files(root, marker.name, {"format.json": _json(dict(
                schema_version="lh-artifact-store-v3", database_identity=current_identity,
                filesystem_binding=dict(schema_version="lh-artifact-filesystem-v1",
                    database_identity=current_identity, filesystem_id=physical["filesystem_id"],
                    checkpoint_sha256=None)))})
        elif create and identity is None:
            _publish_files(marker, "database-identity", {"identity.json": _json(current_identity)})
        if create:
            _sync_directory_ancestry(marker / "database-identity"
                if os.path.lexists(marker / "database-identity") else marker, os.geteuid())
        return ledger
    except BaseException:
        ledger.close()
        raise


def _reserve_task(root, binding, *, create=True):
    """Retain a small independent guard before either database transaction."""
    from .evidence import _open_root, _sync_directory_ancestry
    name = "request-" + _task_name(binding["producer"], binding["operation_id"])
    if not create and not os.path.lexists(root / name):
        return root / name
    if not os.path.lexists(root / "ledger.sqlite"):
        _fail("Previously reserved Ledger is missing; restore the original database")
    expected = _json(dict(binding=binding, database_identity=_database_identity(root / "ledger.sqlite")))
    if os.path.lexists(root / name):
        with _open_root(root / name, os.geteuid()) as fd:
            if _read(root / name / "identity.json", 65536) != expected:
                _fail("Retained task or database identity differs from its original reservation")
            if create:
                os.fsync(fd)
        # Publication may have succeeded before a previous directory sync failed.
        if create:
            _sync_directory_ancestry(root, os.geteuid())
    else:
        _publish_files(root, name, {"identity.json": expected})
    return root / name


def _check_new_task(root, producer, operation_id):
    if os.path.lexists(root / ("request-" + _task_name(producer, operation_id))):
        _fail("Original task recovery directory is missing; restore it before continuing")
    if os.path.lexists(root / "ledger.sqlite") or os.path.lexists(root / "database-initialized"):
        api = _ledger_api()
        with _database(root) as ledger:
            for kind, key in (("create_artifact", "create"), ("append_version", "append")):
                try:
                    ledger.get_operation(_task_scope(producer, operation_id), kind, key)
                except api.LedgerError as error:
                    if error.code != "NOT_FOUND":
                        raise
                else:
                    _fail("This task already has a committed operation; restore its original requests")


def _load_version(ledger, artifact_id, version_id):
    artifact = ledger.get_record("artifact", _identity(artifact_id))
    version = ledger.get_record("version", _identity(version_id))
    if artifact["type_ref"] != TYPE or version["artifact_id"] != artifact_id:
        _fail("Requested version does not belong to this completed-evidence artifact")
    root = ledger.get_record("content_root", version["content_root_ref"])
    if root["kind"] != "manifest":
        _fail("Unsupported archived content layout")
    manifest = ledger.get_record("manifest", root["manifest_ref"])
    entries = manifest["entries"]
    if (len(entries) != len(LIMITS) or {e["entry_key"] for e in entries} != set(LIMITS)
            or manifest["digest"] != {"algorithm": "sha256", "value": _sha(_json(dict(entries=entries)))}):
        _fail("Archived manifest layout or digest differs")
    files = {}
    for entry in entries:
        name, ref = entry["entry_key"], entry["blob_ref"]
        blob = ledger.get_record("blob", ref)
        if blob["byte_length"] > LIMITS[name]:
            _fail("Archived file exceeds the consumer limit", "LIMIT_EXCEEDED")
        raw = ledger.read_blob(ref)
        if len(raw) != blob["byte_length"] or _sha(raw) != blob["digest"]["value"]:
            _fail("Archived bytes differ from their version", "INTEGRITY_FAILURE")
        files[name] = raw
    source = _decode(files["source.json"])
    if _source(files, source.get("producer"), source.get("status_sha256")) != source:
        _fail("Archived source binding differs from its evidence", "INTEGRITY_FAILURE")
    expected_ref = "local-hand:" + source["producer"] + ":" + source["operation_id"]
    if version["external_source_refs"] != [expected_ref]:
        _fail("Archived version source differs from its evidence", "INTEGRITY_FAILURE")
    return files, source


def _resume_locked(root, producer, operation_id):
    from .evidence import _open_root, _sync_directory_ancestry
    _sync_directory_ancestry(root, os.geteuid())
    directory = root / _task_name(producer, operation_id)
    with _open_root(directory, os.geteuid()) as fd:
        binding = _decode(_read(directory / "binding.json", 65536))
        if (binding.get("schema_version") not in ("lh-artifact-request-v1", "lh-artifact-request-v2")
                or binding.get("producer") != producer or binding.get("operation_id") != operation_id):
            _fail("Retained task mapping differs")
        files = {name: _read(directory / name, maximum) for name, maximum in LIMITS.items()}
        source = _source(files, producer, binding["status_sha256"])
        if _json(source) != files["source.json"] or source["operation_id"] != operation_id:
            _fail("Retained evidence source differs")
        create, append, payloads = _requests(binding, files)
        if (_read(directory / "create.json", 65536) != create
                or _read(directory / "append.json", 65536) != append):
            _fail("Retained original request differs")
        os.fsync(fd)
    # Check the independent reservation before initialization can create a
    # replacement database/marker when the global marker has gone missing.
    _reserve_task(root, binding, create=False)
    with _database(root, create=True) as ledger:
        reservation = _reserve_task(root, binding)
        # A retained append confirmation also proves that create must exist,
        # even if create's own receipt was subsequently lost.
        created = _ensure_operation(ledger, create, receipt_directory=reservation,
                                    require_existing=os.path.lexists(reservation / "append_version"))
        appended = _ensure_operation(ledger, append, payloads=payloads, receipt_directory=reservation)
        restored, _ = _load_version(ledger, created["result_ref"], appended["result_ref"])
        if restored != files:
            _fail("Read-back differs from the original request", "INTEGRITY_FAILURE")
    return dict(status="ARCHIVED", artifact_id=created["result_ref"], version_id=appended["result_ref"],
                producer=producer, operation_id=operation_id, recorded_at=appended["recorded_at"],
                reused=appended["replayed"], content_verified=True,
                files={name: dict(size=len(raw), sha256=_sha(raw)) for name, raw in files.items()})


def archive_result(store, *, producer, status_path, status_sha256, evidence_dir):
    _ledger_api()  # Missing optional dependency must not stage a new request.
    files = {"status.json": _read(status_path, LIMITS["status.json"])}
    for name in ("evidence.zip", "evidence.manifest", "evidence.seal"):
        files[name] = _read(Path(evidence_dir) / name, LIMITS[name])
    source = _source(files, producer, status_sha256)
    files["source.json"] = _json(source)
    if len(files["source.json"]) > LIMITS["source.json"]:
        _fail("Archive source metadata exceeds its byte budget", "LIMIT_EXCEEDED")
    operation_id = source["operation_id"]
    with _locked_store(store, create=True) as root:
        name = _task_name(producer, operation_id)
        if os.path.lexists(root / name):
            # A later status observation may have a new timestamp; preserve the
            # first authenticated snapshot, but require the same semantic task,
            # request and seal. Never silently replace the original evidence.
            from .evidence import _open_root
            with _open_root(root / name, os.geteuid()):
                old = _decode(_read(root / name / "source.json", LIMITS["source.json"]))
            if ({k: v for k, v in old.items() if k != "status_sha256"}
                    != {k: v for k, v in source.items() if k != "status_sha256"}):
                _fail("This task is already bound to different evidence")
        else:
            _check_new_task(root, producer, operation_id)
            binding = dict(schema_version="lh-artifact-request-v2", producer=producer,
                           operation_id=operation_id, status_sha256=status_sha256, token=uuid.uuid4().hex)
            create, append, _ = _requests(binding, files)
            _publish_files(root, name, dict(files, **{"binding.json": _json(binding),
                                                      "create.json": create, "append.json": append}))
        return _resume_locked(root, producer, operation_id)


def resume_archive(store, *, producer, operation_id):
    _ledger_api()
    with _locked_store(store) as root:
        return _resume_locked(root, producer, operation_id)


def bind_filesystem(store, *, expected_database_sha256):
    """Add a legacy filesystem binding using a caller's trusted DB checkpoint.

    This never initializes a database, changes requests or executes Ledger
    operations. The old format and every old identity/receipt remain intact.
    """
    from .evidence import _open_root, _sync_directory_ancestry
    api = _ledger_api()
    expected_database_sha256 = _digest(expected_database_sha256)
    with _locked_store(store) as root:
        path = root / "ledger.sqlite"
        physical = _physical_database_identity(path)
        # A checkpoint hash of a live WAL database would omit committed data.
        if any(os.path.lexists(Path(str(path) + suffix)) for suffix in ("-wal", "-shm", "-journal")):
            _fail("Close all database writers and retain sidecars before binding")
        def checkpoint():
            digest = hashlib.sha256()
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                info = os.fstat(fd)
                if (info.st_dev, info.st_ino) != (physical["device"], physical["inode"]):
                    _fail("Ledger changed during filesystem binding")
                while chunk := os.read(fd, 1024 * 1024):
                    digest.update(chunk)
                if digest.hexdigest() != expected_database_sha256:
                    _fail("Ledger differs from the trusted checkpoint", "INTEGRITY_FAILURE")
            finally:
                os.close(fd)
        checkpoint()
        marker = root / "database-initialized"
        with _open_root(marker, os.geteuid()):
            format_record = _decode(_read(marker / "format.json", 4096))
            if format_record == {"schema_version": "lh-artifact-store-v1"}:
                with _open_root(marker / "database-identity", os.geteuid()):
                    identity = _decode(_read(marker / "database-identity/identity.json", 1024))
            elif format_record.get("schema_version") in ("lh-artifact-store-v2", "lh-artifact-store-v3"):
                identity = format_record.get("database_identity")
            else:
                _fail("Unsupported archive store format", "UNSUPPORTED")
        if (not isinstance(identity, dict) or set(identity) != {"device", "inode"}
                or any(type(v) is not int or v < 0 for v in identity.values())
                or identity["inode"] != physical["inode"]):
            _fail("Filesystem binding cannot authorize a replaced database")
        existing = _filesystem_binding(path)
        if existing is not None and _database_identity(path) != identity:
            _fail("Filesystem binding differs from the original identity")
        with api.open(path) as ledger:
            ledger.verify()
            for reservation in root.glob("request-task-*"):
                with _open_root(reservation, os.geteuid()):
                    saved_raw = _read(reservation / "identity.json", 65536)
                    saved = _decode(saved_raw)
                    if saved.get("database_identity") != identity:
                        _fail("Task reservation differs from the original database")
                    binding = saved.get("binding")
                    # resume compares this independent fence byte-for-byte.
                    # Maintenance must not certify a reservation it cannot use.
                    if (not isinstance(binding, dict)
                            or saved_raw != _json(dict(binding=binding, database_identity=identity))):
                        _fail("Task reservation differs from its original bytes", "INTEGRITY_FAILURE")
                    task = root / _task_name(binding["producer"], binding["operation_id"])
                    if reservation.name != "request-" + task.name:
                        _fail("Task reservation name differs from its binding")
                    with _open_root(task, os.geteuid()):
                        if _decode(_read(task / "binding.json", 65536)) != binding:
                            _fail("Original task binding differs")
                        _, create, append = _request_templates(binding)
                        for kind, filename, expected in (("create_artifact", "create.json", create),
                                                        ("append_version", "append.json", append)):
                            # Append also proves create must exist, even if its
                            # receipt was lost. Verification may never repair a
                            # receipt or select another one via a changed kind.
                            if (os.path.lexists(reservation / kind) or
                                    (kind == "create_artifact" and os.path.lexists(reservation / "append_version"))):
                                raw = _read(task / filename, 65536)
                                request = _decode(raw)
                                if (set(request) != set(expected)
                                        or any(request[key] != value for key, value in expected.items() if key != "body")
                                        or not isinstance(request["body"], dict)
                                        or any(request["body"].get(key) != value for key, value in expected["body"].items())):
                                    _fail("Retained request differs from its original task mapping", "INTEGRITY_FAILURE")
                                _ensure_operation(ledger, raw, receipt_directory=reservation, verify_only=True)
        checkpoint()
        if _physical_database_identity(path) != physical:
            _fail("Ledger changed during filesystem binding")
        if any(os.path.lexists(Path(str(path) + suffix)) for suffix in ("-wal", "-shm", "-journal")):
            _fail("Database sidecars appeared during filesystem binding")
        if existing is None:
            _publish_files(marker, "filesystem-binding", {"identity.json": _json(dict(
                schema_version="lh-artifact-filesystem-v1", database_identity=identity,
                filesystem_id=physical["filesystem_id"], checkpoint_sha256=expected_database_sha256))})
        _sync_directory_ancestry(marker, os.geteuid())
        return dict(status="FILESYSTEM_BOUND", reused=existing is not None,
                    checkpoint_sha256=expected_database_sha256, ledger_writes=0)


def _persistent_identity(physical):
    return {key: physical[key] for key in ("filesystem_id", "inode")}


def _recovery_name(physical):
    return "recovered-" + _sha(_json(_persistent_identity(physical)))


def _validate_recovery_binding(record):
    if (set(record) != {"schema_version", "database_identity", "physical_identity",
                       "checkpoint_sha256", "restored_database_sha256"}
            or record["schema_version"] != "lh-artifact-recovered-v1"
            or not isinstance(record["database_identity"], dict)
            or set(record["database_identity"]) != {"device", "inode"}
            or any(type(v) is not int or v < 0 for v in record["database_identity"].values())
            or not isinstance(record["physical_identity"], dict)
            or set(record["physical_identity"]) != {"filesystem_id", "inode"}
            or any(type(v) is not int or v <= 0 for v in record["physical_identity"].values())):
        _fail("Invalid restored database binding", "INTEGRITY_FAILURE")
    _digest(record["checkpoint_sha256"])
    _digest(record["restored_database_sha256"])


def _no_sidecars(path):
    if any(os.path.lexists(Path(str(path) + suffix)) for suffix in ("-wal", "-shm", "-journal")):
        _fail("Close database writers and resolve retained sidecars before this read-only check")


def _file_digest(path, *, max_bytes=1024 * 1024 * 1024):
    """Bounded no-follow checkpoint read; never open SQLite for recovery."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_uid != os.geteuid() or before.st_mode & 0o077
                or before.st_size > 1024 * 1024 * 1024):
            _fail("Recovery inputs must be private bounded regular files")
        if before.st_size > max_bytes:
            _fail("Archive recovery metadata exceeds 1 GiB", "LIMIT_EXCEEDED")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(fd, 1024 * 1024):
            size += len(chunk)
            if size > before.st_size:
                _fail("Recovery input grew during inspection")
            digest.update(chunk)
        def stamp(st):
            return (st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_nlink,
                    st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        if (size != before.st_size or stamp(before) != stamp(os.fstat(fd))
                or stamp(before) != stamp(path.lstat())):
            _fail("Recovery input changed during inspection")
        return dict(size=size, sha256=digest.hexdigest())
    finally:
        os.close(fd)


def _archive_metadata_digest(root, *, ignore=None):
    """Fingerprint published consumer files, excluding DB, lock and failed staging."""
    from .evidence import _open_root
    files = {}
    visited = total = 0
    def walk(directory):
        nonlocal visited, total
        with _open_root(directory, os.geteuid()), os.scandir(directory) as entries:
            for entry in entries:
                child = directory / entry.name
                # Only the one new binding is outside the original inventory;
                # allow its publication retry even at the original entry limit.
                if child == ignore:
                    continue
                visited += 1
                if visited > 4096:
                    _fail("Archive recovery inventory exceeds 4096 entries", "LIMIT_EXCEEDED")
                # Failed staging still costs enumeration resources, even though
                # its unpublished contents are neither traversed nor fingerprinted.
                if (child.name.startswith(".pending-")
                        or (directory == root and child.name in {"ledger.sqlite", ".archive.lock"})):
                    continue
                info = child.lstat()
                if stat.S_ISDIR(info.st_mode):
                    walk(child)
                else:
                    # Reject from the opened file's size before reading payload
                    # that cannot fit in the remaining inventory byte budget.
                    value = _file_digest(child, max_bytes=MAX_RECOVERY_METADATA_BYTES - total)
                    total += value["size"]
                    files[str(child.relative_to(root))] = value
    walk(root)
    return _sha(_json(files))  # Canonical keys preserve traversal-order independence.


def _verify_recovery_requests(root, ledger, *, operation_count):
    """Check retained requests and confirmations without completing a partial task."""
    from .evidence import _open_root
    api = _ledger_api()
    identity = _original_database_identity(root)
    verified_operations = set()
    tasks = {p.name: p for p in root.iterdir() if p.name.startswith("task-")}
    reservations = {p.name: p for p in root.iterdir() if p.name.startswith("request-task-")}
    if any(name.removeprefix("request-") not in tasks for name in reservations):
        _fail("Recovery point is missing original task files", "INTEGRITY_FAILURE")
    for name, task in sorted(tasks.items()):
        with _open_root(task, os.geteuid()):
            binding = _decode(_read(task / "binding.json", 65536))
            ids, _, _ = _request_templates(binding)
            if name != _task_name(binding["producer"], binding["operation_id"]):
                _fail("Recovery task name differs from its original mapping", "INTEGRITY_FAILURE")
            files = {n: _read(task / n, maximum) for n, maximum in LIMITS.items()}
            source = _source(files, binding["producer"], binding["status_sha256"])
            if source["operation_id"] != binding["operation_id"] or _json(source) != files["source.json"]:
                _fail("Recovery evidence differs from the original task", "INTEGRITY_FAILURE")
            create, append, _ = _requests(binding, files)
            if _read(task / "create.json", 65536) != create or _read(task / "append.json", 65536) != append:
                _fail("Recovery request differs from its original evidence", "INTEGRITY_FAILURE")
        reservation = root / ("request-" + name)
        if os.path.lexists(reservation):
            with _open_root(reservation, os.geteuid()):
                if _read(reservation / "identity.json", 65536) != _json(dict(binding=binding, database_identity=identity)):
                    _fail("Recovery reservation differs from its original task", "INTEGRITY_FAILURE")
        append_request = _decode(append)
        try:
            ledger.get_operation(append_request["idempotency_scope_ref"], "append_version", append_request["idempotency_key"])
            append_exists = True
        except api.LedgerError as error:
            if error.code != "NOT_FOUND":
                raise
            append_exists = False
        for raw in (create, append):
            request = _decode(raw)
            kind = request["operation_kind"]
            confirmed = (os.path.lexists(reservation / kind) or
                         (kind == "create_artifact" and (append_exists or os.path.lexists(reservation / "append_version"))))
            try:
                ledger.get_operation(request["idempotency_scope_ref"], kind, request["idempotency_key"])
            except api.LedgerError as error:
                if error.code != "NOT_FOUND":
                    raise
                if confirmed:
                    _fail("Recovery point lacks a confirmed operation", "INTEGRITY_FAILURE")
                continue
            _ensure_operation(ledger, raw, receipt_directory=reservation, verify_only=True)
            verified_operations.add((request["idempotency_scope_ref"], kind, request["idempotency_key"]))
            if kind == "append_version" and _load_version(ledger, ids["artifact"], ids["version"])[0] != files:
                _fail("Recovery payload differs from original evidence", "INTEGRITY_FAILURE")
    # This is a dedicated consumer store: checking only surviving directories
    # misses loss of both a task and its reservation. Every committed operation
    # must resolve to a retained request. Uncommitted staged requests remain valid.
    if len(verified_operations) != operation_count:
        _fail("Recovery point is missing original requests for committed Ledger operations", "INTEGRITY_FAILURE")


def recovery_checkpoint(store):
    """Capture a trusted, quiescent archive through the public Ledger export API."""
    _ledger_api()
    with _locked_store(store, read_only=True) as root:
        path = root / "ledger.sqlite"
        _no_sidecars(path)
        physical = _physical_database_identity(path)
        database = _file_digest(path)
        metadata = _archive_metadata_digest(root)
        with _database(root) as ledger:
            verification = ledger.verify()
            _verify_recovery_requests(root, ledger, operation_count=verification["counts"]["idempotency_records"])
            bundle_digest = _sha(ledger.export_bundle()["package_utf8"])
        identity = _original_database_identity(root)
        if identity is None:
            _fail("An archive recovery checkpoint requires an existing identity guard")
        _no_sidecars(path)
        if (database != _file_digest(path) or physical != _physical_database_identity(path)
                or metadata != _archive_metadata_digest(root)):
            _fail("Archive changed during recovery checkpoint")
        checkpoint = dict(schema_version="lh-artifact-recovery-checkpoint-v1",
                          database_identity=identity, source_database_sha256=database["sha256"],
                          archive_metadata_sha256=metadata, ledger_bundle_sha256=bundle_digest)
        return dict(status="RECOVERY_CHECKPOINT", checkpoint=checkpoint,
                    checkpoint_sha256=_sha(_json(checkpoint)), ledger_writes=0)


def bind_restored(store, *, checkpoint_path, expected_checkpoint_sha256, expected_database_sha256):
    """Explicitly bind a verified restored file; preserve all original identities."""
    from .evidence import _open_root, _sync_directory_ancestry
    api = _ledger_api()
    expected_checkpoint_sha256 = _digest(expected_checkpoint_sha256)
    expected_database_sha256 = _digest(expected_database_sha256)
    envelope = _decode(_read(checkpoint_path, 16384))
    checkpoint = envelope.get("checkpoint")
    if (envelope.get("status") != "RECOVERY_CHECKPOINT" or not isinstance(checkpoint, dict)
            or set(checkpoint) != {"schema_version", "database_identity", "source_database_sha256",
                                   "archive_metadata_sha256", "ledger_bundle_sha256"}
            or checkpoint["schema_version"] != "lh-artifact-recovery-checkpoint-v1"
            or _sha(_json(checkpoint)) != expected_checkpoint_sha256
            or envelope.get("checkpoint_sha256") != expected_checkpoint_sha256):
        _fail("Recovery checkpoint differs from the caller's trusted record", "INTEGRITY_FAILURE")
    for key in ("source_database_sha256", "archive_metadata_sha256", "ledger_bundle_sha256"):
        _digest(checkpoint[key])
    with _locked_store(store) as root:
        path = root / "ledger.sqlite"
        _no_sidecars(path)
        physical = _physical_database_identity(path)
        name = _recovery_name(physical)
        marker = root / "database-initialized"
        target = marker / name
        identity = _original_database_identity(root)
        if identity is None or identity != checkpoint["database_identity"]:
            _fail("Restored archive has a different original identity", "INTEGRITY_FAILURE")
        record = dict(schema_version="lh-artifact-recovered-v1", database_identity=identity,
                      physical_identity=_persistent_identity(physical),
                      checkpoint_sha256=expected_checkpoint_sha256,
                      restored_database_sha256=expected_database_sha256)
        existing = os.path.lexists(target)
        if existing:
            with _open_root(target, os.geteuid()):
                if _decode(_read(target / "identity.json", 4096)) != record:
                    _fail("This restored file already has a different recovery binding")
        def check_inputs():
            _no_sidecars(path)
            if (_physical_database_identity(path) != physical
                    or _file_digest(path)["sha256"] != expected_database_sha256
                    or _archive_metadata_digest(root, ignore=target) != checkpoint["archive_metadata_sha256"]):
                _fail("Restored database or consumer files differ from the selected recovery point", "INTEGRITY_FAILURE")
        check_inputs()
        # Open the replacement only through the public API. Its complete export
        # binds every record, operation and payload, including unconfirmed commits.
        with api.open(path) as ledger:
            verification = ledger.verify()
            _verify_recovery_requests(root, ledger, operation_count=verification["counts"]["idempotency_records"])
            if _sha(ledger.export_bundle()["package_utf8"]) != checkpoint["ledger_bundle_sha256"]:
                _fail("Restored Ledger history or content differs from the checkpoint", "INTEGRITY_FAILURE")
        check_inputs()
        if not existing:
            _publish_files(marker, name, {"identity.json": _json(record)})
        _sync_directory_ancestry(target, os.geteuid())
        if _database_identity(path) != identity:
            _fail("Restored binding could not be read back", "INTEGRITY_FAILURE")
        return dict(status="RESTORED_BOUND", reused=existing, checkpoint_sha256=expected_checkpoint_sha256,
                    restored_database_sha256=expected_database_sha256, ledger_writes=0)


def read_version(store, *, artifact_id, version_id, output):
    from .evidence import _open_root
    _ledger_api()
    output = Path(output).absolute()
    root = Path(store).absolute()
    if output.resolve().is_relative_to(root.resolve()):
        _fail("Read output must be outside the archive store", "INVALID_INPUT")
    with _locked_store(root, read_only=True) as locked:
        _no_sidecars(locked / "ledger.sqlite")
        with _database(locked) as ledger:
            files, source = _load_version(ledger, artifact_id, version_id)
        with _open_root(output.parent, os.geteuid()):
            _publish_files(output.parent, output.name, files)
    return dict(status="READ", artifact_id=artifact_id, version_id=version_id,
                content_verified=True, source=source,
                files={name: dict(size=len(raw), sha256=_sha(raw)) for name, raw in files.items()})


def read_snapshot_version(*, snapshot, expected_manifest_sha256, artifact_id,
                          version_id, output, scratch_parent, storage_config=None):
    """Read one exact artifact version through Ledger's snapshot storage adapter.

    Snapshot identity and logical artifact identity are independent. The caller
    supplies the manifest digest from the original snapshot receipt. A NAS input
    needs its private storage binding; no NAS database is opened by this consumer.
    Output is a new local restore directory, retained after success or failure.
    This does not initialize/rebind an archive store or replay an execution.
    """
    api = _ledger_api()
    from infra_artifact_ledger import recovery
    expected_manifest_sha256 = _digest(expected_manifest_sha256)
    artifact_id, version_id = _identity(artifact_id), _identity(version_id)
    output = Path(output).absolute()
    # Apply the receipt publisher's path rule before restore can create output.
    # Do not resolve away components that may traverse a symbolic link.
    if ".." in output.parts:
        _fail("Snapshot read output must not contain parent traversal", "INVALID_INPUT")
    config = None if storage_config is None else _decode(_read(storage_config, 16384))
    restored = recovery.restore(snapshot=snapshot, target_dir=output,
        expected_manifest_sha256=expected_manifest_sha256,
        scratch_parent=scratch_parent, storage_config=config)
    # The public restore API validated a fresh local target and all snapshot
    # members before publishing it. Preserve its response before further reads.
    _publish_files(output, "snapshot-receipt", {"restore.json": _json(restored)})
    database = output / "ledger.sqlite"
    before = _file_digest(database)
    if before["sha256"] != restored["data"]["database_sha256"]:
        _fail("Restored database differs from the snapshot receipt", "INTEGRITY_FAILURE")
    with api.open(database) as ledger:
        files, source = _load_version(ledger, artifact_id, version_id)
    if _file_digest(database) != before:
        _fail("Restored database changed during content read", "INTEGRITY_FAILURE")
    _publish_files(output, "evidence", files)
    result = dict(status="READ", artifact_id=artifact_id, version_id=version_id,
        content_verified=True, source=source, snapshot_id=restored["data"]["snapshot_id"],
        manifest_sha256=expected_manifest_sha256, database_sha256=before["sha256"],
        evidence_directory=str(output / "evidence"),
        storage_ref=None if config is None else config["storage_ref"],
        files={name: dict(size=len(raw), sha256=_sha(raw)) for name, raw in files.items()})
    _publish_files(output, "read-receipt", {"result.json": _json(result)})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("archive", help="Archive retained completed task evidence")
    write.add_argument("--store", required=True)
    write.add_argument("--producer", required=True, help="Stable identity of the source Local Hand instance")
    write.add_argument("--status", required=True, dest="status_path")
    write.add_argument("--status-sha256", required=True, help="Digest from the trusted retained tool response")
    write.add_argument("--evidence-dir", required=True)
    resume = commands.add_parser("resume", help="Reconcile original staged requests without source files")
    resume.add_argument("--store", required=True)
    resume.add_argument("--producer", required=True)
    resume.add_argument("--operation-id", required=True)
    bind = commands.add_parser("bind-filesystem", help="Bind a legacy store using a trusted database checkpoint")
    bind.add_argument("--store", required=True)
    bind.add_argument("--expected-database-sha256", required=True)
    checkpoint = commands.add_parser("recovery-checkpoint", help="Capture a quiescent archive recovery checkpoint")
    checkpoint.add_argument("--store", required=True)
    restored = commands.add_parser("bind-restored", help="Explicitly bind a restored archive to its trusted checkpoint")
    restored.add_argument("--store", required=True)
    restored.add_argument("--checkpoint", dest="checkpoint_path", required=True)
    restored.add_argument("--expected-checkpoint-sha256", required=True)
    restored.add_argument("--expected-database-sha256", required=True)
    read = commands.add_parser("read", help="Read an exact version into a new private directory")
    for name in ("store", "artifact-id", "version-id", "output"):
        read.add_argument("--" + name, required=True)
    snapshot_read = commands.add_parser("read-snapshot", help="Read an exact version from a local or NAS Ledger snapshot")
    for name in ("snapshot", "expected-manifest-sha256", "artifact-id", "version-id", "output", "scratch-parent"):
        snapshot_read.add_argument("--" + name, required=True)
    snapshot_read.add_argument("--storage-config", help="Private mounted-storage binding; required for NAS input")
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        result = {"archive": archive_result, "resume": resume_archive, "read": read_version,
                  "bind-filesystem": bind_filesystem, "recovery-checkpoint": recovery_checkpoint,
                  "bind-restored": bind_restored, "read-snapshot": read_snapshot_version}[command](**args)
    except Exception as error:
        # Preserve any Ledger commit_state. Generic failures can follow a commit;
        # a nonzero exit never means the original task or archive write rolled back.
        result = dict(status="ERROR", code=getattr(error, "code", "UNCONFIRMED"),
                      commit_state=getattr(error, "commit_state", "unknown"),
                      message=str(error) if isinstance(error, (ArchiveError, LocalHandError, JobError))
                      or hasattr(error, "commit_state") or hasattr(error, "publication_state")
                      else "Local archive failed; retain the store and reconcile the original request")
        if hasattr(error, "publication_state"):
            result["publication_state"] = error.publication_state
            result["stage"] = getattr(error, "stage", None)
        print(_json(result).decode("utf-8"))
        return 1
    print(_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
