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


MAX_BLOB = 64 * 1024 * 1024
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


def _database_identity(path):
    info = path.lstat()
    return dict(device=info.st_dev, inode=info.st_ino)


@contextmanager
def _locked_store(store, *, create=False):
    if sys.platform != "linux":
        _fail("Local artifact archives currently support Linux only", "UNSUPPORTED")
    import fcntl
    from .evidence import _open_root, _sync_directory_ancestry
    root = Path(store).absolute()
    with _open_root(root, os.geteuid(), create=create) as directory:
        flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
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


def _requests(binding, files):
    token = binding["token"]
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
    entries, blobs, payloads = [], [], {}
    for number, name in enumerate(sorted(LIMITS)):
        ref = "blob:" + token + ":" + str(number)
        entries.append(dict(entry_key=name, blob_ref=ref))
        blobs.append(dict(blob_ref=ref, digest=dict(algorithm="sha256", value=_sha(files[name])),
                          byte_length=len(files[name]), payload_availability="available"))
        payloads[ref] = files[name]
    source_ref = "local-hand:" + binding["producer"] + ":" + binding["operation_id"]
    if len(source_ref) > 512:
        _fail("Combined source identity exceeds the Ledger reference limit", "LIMIT_EXCEEDED")
    append = dict(base, operation_kind="append_version", idempotency_key="append",
        body=dict(version=dict(version_id=ids["version"], artifact_id=ids["artifact"],
            content_root_ref=ids["root"], parent_version_refs=[], external_source_refs=[source_ref],
            capture_refs=[], handling_policy_refs=[]),
            content_roots=[dict(content_root_ref=ids["root"], kind="manifest", manifest_ref=ids["manifest"])],
            manifests=[dict(manifest_ref=ids["manifest"], entries=entries,
                            digest=dict(algorithm="sha256", value=_sha(_json(dict(entries=entries)))))],
            blobs=blobs, provenance_links=[]))
    return _json(create), _json(append), payloads


def _fingerprint(request):
    # Public bounded-local-v0.1 fingerprint algorithm; no private Ledger imports.
    return {"algorithm": "sha256", "value": _sha(_json({key: request[key] for key in
        ("contract_version", "idempotency_scope_ref", "operation_kind", "body")}))}


def _ensure_operation(ledger, raw, *, payloads=None):
    api = _ledger_api()
    request = _decode(raw)
    kind = request["operation_kind"]
    result_kind, id_field = ("artifact", "artifact_id") if kind == "create_artifact" else ("version", "version_id")
    expected = request["body"][result_kind]
    try:
        previous = ledger.get_operation(request["idempotency_scope_ref"], kind, request["idempotency_key"])
    except api.LedgerError as error:
        if error.code != "NOT_FOUND":
            raise
    else:
        record = previous["idempotency_record"]
        if (any(record[key] != request[key] for key in
                ("idempotency_scope_ref", "operation_kind", "idempotency_key"))
                or record["request_fingerprint"] != _fingerprint(request)
                or record["result_ref"] != expected[id_field]
                or any(previous["result"].get(key) != value for key, value in expected.items())):
            _fail("Stored operation differs from the retained request", "IDEMPOTENCY_CONFLICT")
        return dict(status="COMMITTED", commit_state="committed", operation_kind=kind,
                    result_ref=record["result_ref"], recorded_at=record["recorded_at"], replayed=True)
    # The process holding the cooperative lock owns the synchronous connection.
    # NOT_FOUND permits only this exact original request, never a new identity.
    result = ledger.execute(raw, **({"payloads": payloads} if payloads is not None else {}))
    if (result.get("status") != "COMMITTED" or result.get("commit_state") != "committed"
            or result.get("result_ref") != expected[id_field]):
        raise ArchiveError("UNCONFIRMED", "Ledger response did not confirm the original request", "unknown")
    return result


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
    identity = None
    if os.path.lexists(marker):
        with _open_root(marker, os.geteuid()):
            format_record = _decode(_read(marker / "format.json", 1024))
            if format_record.get("schema_version") == "lh-artifact-store-v2":
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
            _publish_files(root, marker.name, {"format.json": _json(dict(
                schema_version="lh-artifact-store-v2", database_identity=current_identity))})
        elif create and identity is None:
            _publish_files(marker, "database-identity", {"identity.json": _json(current_identity)})
        if create:
            _sync_directory_ancestry(marker / "database-identity"
                if os.path.lexists(marker / "database-identity") else marker, os.geteuid())
        return ledger
    except BaseException:
        ledger.close()
        raise


def _reserve_task(root, binding):
    """Retain a small independent guard before either database transaction."""
    from .evidence import _open_root, _sync_directory_ancestry
    name = "request-" + _task_name(binding["producer"], binding["operation_id"])
    expected = _json(dict(binding=binding, database_identity=_database_identity(root / "ledger.sqlite")))
    if os.path.lexists(root / name):
        with _open_root(root / name, os.geteuid()) as fd:
            if _read(root / name / "identity.json", 65536) != expected:
                _fail("Retained task or database identity differs from its original reservation")
            os.fsync(fd)
        # Publication may have succeeded before a previous directory sync failed.
        _sync_directory_ancestry(root, os.geteuid())
    else:
        _publish_files(root, name, {"identity.json": expected})


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
    with _database(root, create=True) as ledger:
        _reserve_task(root, binding)
        created = _ensure_operation(ledger, create)
        appended = _ensure_operation(ledger, append, payloads=payloads)
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


def read_version(store, *, artifact_id, version_id, output):
    from .evidence import _open_root
    _ledger_api()
    output = Path(output).absolute()
    root = Path(store).absolute()
    if output.resolve().is_relative_to(root.resolve()):
        _fail("Read output must be outside the archive store", "INVALID_INPUT")
    with _locked_store(root) as locked:
        with _database(locked) as ledger:
            files, source = _load_version(ledger, artifact_id, version_id)
        with _open_root(output.parent, os.geteuid()):
            _publish_files(output.parent, output.name, files)
    return dict(status="READ", artifact_id=artifact_id, version_id=version_id,
                content_verified=True, source=source,
                files={name: dict(size=len(raw), sha256=_sha(raw)) for name, raw in files.items()})


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
    read = commands.add_parser("read", help="Read an exact version into a new private directory")
    for name in ("store", "artifact-id", "version-id", "output"):
        read.add_argument("--" + name, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        result = {"archive": archive_result, "resume": resume_archive, "read": read_version}[command](**args)
    except Exception as error:
        # Preserve any Ledger commit_state. Generic failures can follow a commit;
        # a nonzero exit never means the original task or archive write rolled back.
        result = dict(status="ERROR", code=getattr(error, "code", "UNCONFIRMED"),
                      commit_state=getattr(error, "commit_state", "unknown"),
                      message=str(error) if isinstance(error, (ArchiveError, LocalHandError))
                      or hasattr(error, "commit_state") else "Local archive failed; retain the store and reconcile the original request")
        print(_json(result).decode("utf-8"))
        return 1
    print(_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
