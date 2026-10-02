"""Public-safe offline contract for the private old-producer parser repair.

This module never imports, compiles, or executes the private helper. A caller
may supply the pinned original and repaired bytes to prove that the repair is
one exact insertion and that every caller byte is unchanged. The parser model
deliberately preserves the original mapping rules and adds only the approved
four ``setdefault`` operations. Command execution is represented only by an
injected callable used by isolated tests and future non-field assembly.
"""
from __future__ import annotations

from collections.abc import Mapping
import copy
import hashlib
import io
import json
import os
import re
import stat
import zipfile


RULE = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
BASELINE = "68424df2ddbf812b9479ffa7a64dcaa59a2a9f76"
CLOSURE = "179652cb9487163d83c004d358e4d4b49409694c"
SCOPE = "LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1"

REPAIR_SCOPE = "LH-Q2-SYSTEM-MANAGER-REPAIR-v1"
REPAIR_BASELINE = "ae50aea2639c32021794ecb70730f4b9e781c8d6"
REPAIR_CLOSURE = "23702d6e55396d7941389817ab875a4610d3e142"
PRODUCT_COMMIT = "1a900e4a38e9567655f21cbf3c3f17941de1a8d5"
SOURCE_PACKAGE_NAME = "local-hand-system-manager-1a900e4-20261001e-corrected.zip"
SOURCE_PACKAGE_SHA256 = "5805dcd2a45f150f0e5b7062a17b46137d53e889e1ea160601d7c75fb529e886"

REPAIR_ZIP_BYTES = 12864
REPAIR_ZIP_SHA256 = "2ddb55db15f73738116377de6fb8fa8fba9c5cc2cf23f1f59e2dc112ce63be70"
REPAIR_JSON_BYTES = 1781
REPAIR_JSON_SHA256 = "df3f0e2172e9a92fee7e335fe0c21cad75e7a0b1e3e35978fbb31cf7d5b0438c"
SHA256SUMS_BYTES = 161
SHA256SUMS_SHA256 = "7e03618e4f1b5c5433ba19de4b8d3452d518d7c0eed213511aec3116072385e1"
ORIGINAL_HELPER_BYTES = 39623
PATCHED_HELPER_BYTES = 39976
ORIGINAL_HELPER_SHA256 = "4014a80998469607f8a279a4fc7b7abbeff61e349657b7d8224429d142dfa8db"
PATCHED_HELPER_SHA256 = "3e6521f6065a3bb61e12b0f2cdcbf1c7f2d40e138269bf85d386aeb2741ab21a"
INSERT_OFFSET = 28558
INSERT_BYTES = 353
INSERT_SHA256 = "0fc6d020b99346e159de5496b82f1c5dbd268bae179d1f7934545aaf4511c39e"
PREFIX_SHA256 = "d361402ddd68256bec214ff85ac831f3b6e4c8b9140980b761221c4fb9f5eacb"
SUFFIX_BYTES = 11065
SUFFIX_SHA256 = "7e1e7a756c3b7c07360c96cc967410550b10273aa88814e8338fba36340b2cd9"
REPAIR_CREATED_AT = "2026-10-02T01:19:50.549339+00:00"

REPAIR_MEMBERS = ("REPAIR.json", "SHA256SUMS", "old_producers.py")
EMPTY_EXEC_FIELDS = ("ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost")
SHOW_PROPERTIES = (
    "Id", "LoadState", "ActiveState", "SubState", "MainPID", "ControlPID",
    "ControlGroup", "InvocationID", "Job", "Restart", "NRestarts", "OnSuccess",
    "OnFailure", "Triggers", "TriggeredBy", "ExecStart", *EMPTY_EXEC_FIELDS,
    "FragmentPath", "DropInPaths",
)
SHOW_CHUNK_SIZE = 16
MAX_SHOW_UNITS = 128
COMMAND_MAX_STDOUT = 65536
COMMAND_MAX_STDERR = 65536
COMMAND_MAX_TIMEOUT_SECONDS = 20
REPORT_SCHEMA = "local-hand-q2-old-producer-admission-retry-patch/v1"
_UNIT = re.compile(r"[A-Za-z0-9_.@:-]+\.service")
_SUM = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)\n")


class PatchContractError(ValueError):
    """A stable, content-free refusal from the offline patch contract."""


def _require(condition, reason):
    if not condition:
        raise PatchContractError("OLD_PRODUCER_PATCH_" + reason)


def sha256(raw):
    _require(type(raw) is bytes, "BYTES")
    return hashlib.sha256(raw).hexdigest()


def _unique(pairs):
    value = {}
    for key, item in pairs:
        _require(type(key) is str and key not in value, "JSON_DUPLICATE_KEY")
        value[key] = item
    return value


def _noninteger(_value):
    raise PatchContractError("OLD_PRODUCER_PATCH_JSON_NUMBER")


def _document(raw, maximum):
    _require(type(raw) is bytes and 0 < len(raw) <= maximum, "JSON_BYTES")
    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(text, object_pairs_hook=_unique,
            parse_float=_noninteger, parse_constant=_noninteger)
    except PatchContractError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise PatchContractError("OLD_PRODUCER_PATCH_JSON") from None
    _require(type(value) is dict, "JSON_OBJECT")
    return value


def _same(value, expected):
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return (set(value) == set(expected)
            and all(_same(value[key], expected[key]) for key in expected))
    if isinstance(expected, list):
        return len(value) == len(expected) and all(_same(a, b) for a, b in zip(value, expected))
    return value == expected


def expected_repair_document():
    """Return the exact public metadata contract, never private helper bytes."""
    return {
        "authorization": {"A": REPAIR_BASELINE, "C": REPAIR_CLOSURE, "R": RULE},
        "boundaries": {
            "contains_task_txt": False,
            "field_execution_authorized": False,
            "field_execution_performed": False,
            "guest_contacted": False,
            "new_unique_batch_and_explicit_execution_authority_required": True,
            "raw_field_evidence_included": False,
        },
        "created_at": REPAIR_CREATED_AT,
        "helper": {
            "change": {
                "all_other_fields_synthesized": False,
                "nonempty_hooks_still_rejected": True,
                "normalize_missing_empty_exec_arrays": list(EMPTY_EXEC_FIELDS),
            },
            "name": "old_producers.py",
            "original_sha256": ORIGINAL_HELPER_SHA256,
            "patched_sha256": PATCHED_HELPER_SHA256,
        },
        "product_source": {"changed": False, "commit": PRODUCT_COMMIT},
        "retained_field_result": {
            "batch": "20261001e",
            "consumed": True,
            "normal_chain_executions": 0,
            "retry_authorized": False,
            "status": "FAILED_RETAINED",
        },
        "schema": "local-hand-private-helper-repair/v1",
        "scope": REPAIR_SCOPE,
        "source_package": {"name": SOURCE_PACKAGE_NAME, "sha256": SOURCE_PACKAGE_SHA256},
        # This is the immutable legacy status embedded in the pinned private
        # archive.  The public verifier below deliberately reports the narrower
        # archive-pin status and reserves adoption for verify_repair_adoption().
        "status": "OFFLINE_REPAIR_VERIFIED",
        "validation": {
            "failures": 0,
            "python": "3.12.14",
            "syntax": "PASS",
            "synthetic_caller_and_fail_closed_cases": 11,
            "synthetic_parser_cases": 4,
        },
    }


def parse_repair_json(raw):
    value = _document(raw, 4096)
    _require(_same(value, expected_repair_document()), "REPAIR_JSON_CONTRACT")
    return copy.deepcopy(value)


def _member_contract():
    return {
        "REPAIR.json": (REPAIR_JSON_BYTES, REPAIR_JSON_SHA256),
        "SHA256SUMS": (SHA256SUMS_BYTES, SHA256SUMS_SHA256),
        "old_producers.py": (PATCHED_HELPER_BYTES, PATCHED_HELPER_SHA256),
    }


def parse_sha256sums(raw):
    _require(type(raw) is bytes and len(raw) == SHA256SUMS_BYTES
        and sha256(raw) == SHA256SUMS_SHA256, "SHA256SUMS_PIN")
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeDecodeError:
        raise PatchContractError("OLD_PRODUCER_PATCH_SHA256SUMS_ENCODING") from None
    rows = []
    for line in text.splitlines(keepends=True):
        match = _SUM.fullmatch(line)
        _require(match is not None, "SHA256SUMS_FORMAT")
        rows.append((match.group(2), match.group(1)))
    expected = [("REPAIR.json", REPAIR_JSON_SHA256), ("old_producers.py", PATCHED_HELPER_SHA256)]
    _require(rows == expected, "SHA256SUMS_CONTENT")
    return dict(rows)


def verify_helper_pair(original_raw, patched_raw):
    """Prove one exact insertion while never compiling or executing either helper."""
    _require(type(original_raw) is bytes and type(patched_raw) is bytes, "HELPER_BYTES")
    _require(len(original_raw) == ORIGINAL_HELPER_BYTES
        and sha256(original_raw) == ORIGINAL_HELPER_SHA256, "ORIGINAL_HELPER_PIN")
    _require(len(patched_raw) == PATCHED_HELPER_BYTES
        and sha256(patched_raw) == PATCHED_HELPER_SHA256, "PATCHED_HELPER_PIN")
    prefix = original_raw[:INSERT_OFFSET]
    suffix = original_raw[INSERT_OFFSET:]
    inserted = patched_raw[INSERT_OFFSET:INSERT_OFFSET + INSERT_BYTES]
    _require(len(prefix) == INSERT_OFFSET and sha256(prefix) == PREFIX_SHA256,
        "HELPER_PREFIX_PIN")
    _require(len(suffix) == SUFFIX_BYTES and sha256(suffix) == SUFFIX_SHA256,
        "HELPER_SUFFIX_PIN")
    _require(len(inserted) == INSERT_BYTES and sha256(inserted) == INSERT_SHA256,
        "HELPER_INSERT_PIN")
    _require(patched_raw[:INSERT_OFFSET] == prefix
        and patched_raw[INSERT_OFFSET + INSERT_BYTES:] == suffix,
        "HELPER_CALLER_BYTES_CHANGED")
    return {"original_bytes": ORIGINAL_HELPER_BYTES,
        "original_sha256": ORIGINAL_HELPER_SHA256,
        "patched_bytes": PATCHED_HELPER_BYTES,
        "patched_sha256": PATCHED_HELPER_SHA256,
        "change": {"kind": "EXACT_INSERTION", "offset": INSERT_OFFSET,
            "bytes": INSERT_BYTES, "sha256": INSERT_SHA256},
        "unchanged_prefix_bytes": INSERT_OFFSET,
        "unchanged_suffix_bytes": SUFFIX_BYTES,
        "all_other_helper_bytes_unchanged": True}


def verify_repair_zip_bytes(raw):
    """Verify the exact retained, non-executable repair ZIP entirely in memory."""
    _require(type(raw) is bytes and len(raw) == REPAIR_ZIP_BYTES
        and sha256(raw) == REPAIR_ZIP_SHA256, "REPAIR_ZIP_PIN")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw), "r")
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile):
        raise PatchContractError("OLD_PRODUCER_PATCH_REPAIR_ZIP") from None
    files = {}
    try:
        infos = archive.infolist()
        _require(tuple(info.filename for info in infos) == REPAIR_MEMBERS, "REPAIR_MEMBERS")
        _require(archive.comment == b"", "REPAIR_ZIP_COMMENT")
        contract = _member_contract()
        for info in infos:
            expected_bytes, expected_sha = contract[info.filename]
            mode = info.external_attr >> 16
            _require(info.create_system == 3 and stat.S_ISREG(mode)
                and stat.S_IMODE(mode) == 0o600, "REPAIR_MEMBER_MODE")
            _require(info.compress_type == zipfile.ZIP_DEFLATED and not info.flag_bits & 1
                and not info.extra and not info.comment, "REPAIR_MEMBER_ENCODING")
            _require(info.file_size == expected_bytes and 0 < info.compress_size <= REPAIR_ZIP_BYTES,
                "REPAIR_MEMBER_SIZE")
            try:
                member = archive.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile):
                raise PatchContractError("OLD_PRODUCER_PATCH_REPAIR_MEMBER_READ") from None
            _require(len(member) == expected_bytes and sha256(member) == expected_sha,
                "REPAIR_MEMBER_PIN")
            files[info.filename] = member
        _require(archive.testzip() is None, "REPAIR_MEMBER_CRC")
    finally:
        archive.close()
    sums = parse_sha256sums(files["SHA256SUMS"])
    repair = parse_repair_json(files["REPAIR.json"])
    _require(sums["REPAIR.json"] == sha256(files["REPAIR.json"])
        and sums["old_producers.py"] == sha256(files["old_producers.py"]), "REPAIR_SUM_BINDING")
    return {
        "schema": REPORT_SCHEMA,
        "scope": SCOPE,
        "authority": {"rule": RULE, "baseline": BASELINE, "closure": CLOSURE},
        "status": "OFFLINE_REPAIR_ARCHIVE_PIN_VERIFIED",
        "archive": {"bytes": len(raw), "sha256": sha256(raw)},
        "members": list(REPAIR_MEMBERS),
        "helper": copy.deepcopy(repair["helper"]),
        "contains_task_txt": False,
        "field_execution_authorized": False,
        "field_execution_performed": False,
        "guest_contacted": False,
    }


def _read_explicit_path(path):
    _require(not isinstance(path, int), "REPAIR_PATH")
    try:
        name = os.fspath(path)
    except TypeError:
        raise PatchContractError("OLD_PRODUCER_PATCH_REPAIR_PATH") from None
    _require(type(name) in (str, bytes) and bool(name), "REPAIR_PATH")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(name, flags)
    except OSError:
        raise PatchContractError("OLD_PRODUCER_PATCH_REPAIR_PATH_OPEN") from None
    try:
        before = os.fstat(fd)
        _require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o600
            and before.st_uid == os.geteuid() and before.st_gid == os.getegid()
            and before.st_nlink == 1 and before.st_size == REPAIR_ZIP_BYTES,
            "REPAIR_PATH_FILE")
        pieces, total = [], 0
        while total <= REPAIR_ZIP_BYTES:
            part = os.read(fd, min(65536, REPAIR_ZIP_BYTES + 1 - total))
            if not part:
                break
            pieces.append(part)
            total += len(part)
        after = os.fstat(fd)
        stable = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink",
            "st_size", "st_mtime_ns", "st_ctime_ns")
        _require(total == REPAIR_ZIP_BYTES
            and all(getattr(before, key) == getattr(after, key) for key in stable), "REPAIR_PATH_CHANGED")
        return b"".join(pieces)
    finally:
        os.close(fd)


def verify_repair_zip_path(path):
    """Verify only the explicit caller-selected path; no discovery is performed."""
    return verify_repair_zip_bytes(_read_explicit_path(path))


def verify_repair_adoption(original_helper_raw, repair_zip_raw):
    """Bind the pinned archive to the pinned original by the exact insertion.

    The archive-only verifier deliberately makes no adoption claim.  This
    combined API additionally proves the original/repaired byte relationship,
    while still never compiling or executing either helper and never returning
    their contents.
    """
    archive = verify_repair_zip_bytes(repair_zip_raw)
    try:
        with zipfile.ZipFile(io.BytesIO(repair_zip_raw), "r") as source:
            patched_helper_raw = source.read("old_producers.py")
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile, KeyError):
        raise PatchContractError("OLD_PRODUCER_PATCH_REPAIR_MEMBER_READ") from None
    pair = verify_helper_pair(original_helper_raw, patched_helper_raw)
    return {
        "schema": REPORT_SCHEMA,
        "scope": SCOPE,
        "authority": {"rule": RULE, "baseline": BASELINE, "closure": CLOSURE},
        "status": "OFFLINE_REPAIR_ADOPTION_VERIFIED",
        "archive": archive["archive"],
        "helper_pair": pair,
        "contains_task_txt": False,
        "field_execution_authorized": False,
        "field_execution_performed": False,
        "guest_contacted": False,
    }


def _unit_names(names):
    _require(type(names) in (list, tuple) and len(names) <= MAX_SHOW_UNITS, "UNIT_NAMES")
    result = tuple(names)
    _require(all(type(name) is str and _UNIT.fullmatch(name) for name in result), "UNIT_NAME")
    _require(len(set(result)) == len(result), "UNIT_NAME_DUPLICATE")
    return result


def normalize_show_row(row):
    """Apply only the four approved defaults; do not harden the old parser."""
    _require(isinstance(row, Mapping) and all(type(key) is str and type(value) is str
        for key, value in row.items()), "SHOW_ROW")
    result = dict(row)
    for name in EMPTY_EXEC_FIELDS:
        result.setdefault(name, "")
    return result


def require_empty_exec_hooks(row):
    """Model the unchanged downstream callers' fail-closed hook check."""
    result = normalize_show_row(row)
    _require(all(result[name] == "" for name in EMPTY_EXEC_FIELDS), "EXEC_HOOK_NONEMPTY")
    return result


def parse_show_output(raw, expected_names):
    """Model the original mapping rules plus only the four approved defaults."""
    expected = _unit_names(expected_names)
    _require(type(raw) is bytes and len(raw) <= COMMAND_MAX_STDOUT, "SHOW_BYTES")
    if not expected:
        _require(raw == b"", "SHOW_UNEXPECTED_OUTPUT")
        return {}
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        raise PatchContractError("OLD_PRODUCER_PATCH_SHOW_UTF8") from None
    rows = {}
    for block in text.strip().split("\n\n"):
        row = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        row = normalize_show_row(row)
        _require(row.get("Id") in expected and row["Id"] not in rows,
            "UNIT_OUTPUT_IDENTITY")
        rows[row["Id"]] = row
    _require(set(rows) == set(expected), "UNIT_OUTPUT_INCOMPLETE")
    return rows


def query_show_rows(runner, names, *, ordinary=False):
    """Collect injected responses in the original 16-unit chunks.

    ``runner`` receives the original maximum timeout/stdout/stderr allowances
    in addition to ``ordinary`` and must return the exact mapping
    ``returncode/stdout/stderr``. This function never constructs an argv or
    invokes a process itself.
    """
    expected = _unit_names(names)
    _require(callable(runner) and type(ordinary) is bool, "SHOW_RUNNER")
    rows = {}
    for offset in range(0, len(expected), SHOW_CHUNK_SIZE):
        chunk = expected[offset:offset + SHOW_CHUNK_SIZE]
        try:
            response = runner(chunk, ordinary=ordinary,
                max_timeout_seconds=COMMAND_MAX_TIMEOUT_SECONDS,
                max_stdout=COMMAND_MAX_STDOUT, max_stderr=COMMAND_MAX_STDERR)
        except Exception:
            raise PatchContractError("OLD_PRODUCER_PATCH_SHOW_RUNNER_FAILED") from None
        _require(isinstance(response, Mapping)
            and set(response) == {"returncode", "stdout", "stderr"}, "SHOW_RESULT")
        code, stdout, stderr = response["returncode"], response["stdout"], response["stderr"]
        _require(type(code) is int and type(stdout) is bytes and type(stderr) is bytes,
            "SHOW_RESULT_TYPE")
        _require(len(stdout) <= COMMAND_MAX_STDOUT and len(stderr) <= COMMAND_MAX_STDERR,
            "SHOW_OUTPUT_LIMIT")
        _require(code == 0, "SHOW_COMMAND_FAILED")
        parsed = parse_show_output(stdout, chunk)
        _require(not set(rows).intersection(parsed), "UNIT_OUTPUT_IDENTITY")
        rows.update(parsed)
    _require(set(rows) == set(expected), "UNIT_OUTPUT_INCOMPLETE")
    return rows
