"""Offline tests for the approved old-producer four-field parser contract."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import zipfile

import pytest


SOURCE = Path(__file__).parent / "e3_host/q2_old_producer_admission_retry_patch.py"


def module():
    spec = importlib.util.spec_from_file_location("_old_producer_admission_retry_patch_test", SOURCE)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def show_row(value, name="example.service", *, omit=()):
    row = {key: "" for key in value.SHOW_PROPERTIES if key not in omit}
    row.update({
        "Id": name,
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "SubState": "dead",
        "MainPID": "0",
        "ControlPID": "0",
        "ControlGroup": "",
        "InvocationID": "",
        "Job": "0",
        "Restart": "no",
        "NRestarts": "0",
        "ExecStart": "{ path=/usr/bin/true ; argv[]=/usr/bin/true ; }",
        "FragmentPath": "/etc/systemd/system/" + name,
    })
    for key in omit:
        row.pop(key, None)
    return row


def show_wire(rows):
    return ("\n\n".join("\n".join(key + "=" + item for key, item in row.items())
        for row in rows) + "\n").encode()


def write_zip(files, *, modes=None, compression=zipfile.ZIP_DEFLATED):
    modes = {} if modes is None else modes
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as archive:
        for name, raw in files:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 2, 9, 19, 50))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | modes.get(name, 0o600)) << 16
            info.compress_type = compression
            archive.writestr(info, raw)
    return target.getvalue()


@pytest.fixture
def synthetic_archive(monkeypatch):
    """Build an inert fixture; no byte from the private helper is checked in."""
    value = module()
    prefix = b"synthetic unchanged prefix\n"
    inserted = b"synthetic approved insertion\n"
    suffix = b"synthetic unchanged caller suffix\n"
    original = prefix + suffix
    patched = prefix + inserted + suffix
    monkeypatch.setattr(value, "ORIGINAL_HELPER_BYTES", len(original))
    monkeypatch.setattr(value, "ORIGINAL_HELPER_SHA256", hashlib.sha256(original).hexdigest())
    monkeypatch.setattr(value, "PATCHED_HELPER_SHA256", hashlib.sha256(patched).hexdigest())
    monkeypatch.setattr(value, "PATCHED_HELPER_BYTES", len(patched))
    monkeypatch.setattr(value, "INSERT_OFFSET", len(prefix))
    monkeypatch.setattr(value, "INSERT_BYTES", len(inserted))
    monkeypatch.setattr(value, "INSERT_SHA256", hashlib.sha256(inserted).hexdigest())
    monkeypatch.setattr(value, "PREFIX_SHA256", hashlib.sha256(prefix).hexdigest())
    monkeypatch.setattr(value, "SUFFIX_BYTES", len(suffix))
    monkeypatch.setattr(value, "SUFFIX_SHA256", hashlib.sha256(suffix).hexdigest())
    repair = json.dumps(value.expected_repair_document(), sort_keys=True,
        separators=(",", ":")).encode()
    monkeypatch.setattr(value, "REPAIR_JSON_BYTES", len(repair))
    monkeypatch.setattr(value, "REPAIR_JSON_SHA256", hashlib.sha256(repair).hexdigest())
    sums = (value.REPAIR_JSON_SHA256 + "  REPAIR.json\n"
        + value.PATCHED_HELPER_SHA256 + "  old_producers.py\n").encode()
    monkeypatch.setattr(value, "SHA256SUMS_BYTES", len(sums))
    monkeypatch.setattr(value, "SHA256SUMS_SHA256", hashlib.sha256(sums).hexdigest())
    files = [("REPAIR.json", repair), ("SHA256SUMS", sums), ("old_producers.py", patched)]
    raw = write_zip(files)
    monkeypatch.setattr(value, "REPAIR_ZIP_BYTES", len(raw))
    monkeypatch.setattr(value, "REPAIR_ZIP_SHA256", hashlib.sha256(raw).hexdigest())
    return value, original, patched, repair, sums, files, raw


def repin_archive(monkeypatch, value, raw):
    monkeypatch.setattr(value, "REPAIR_ZIP_BYTES", len(raw))
    monkeypatch.setattr(value, "REPAIR_ZIP_SHA256", hashlib.sha256(raw).hexdigest())


def test_authority_and_private_artifact_pins_are_exact():
    value = module()
    assert value.RULE == "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
    assert value.BASELINE == "68424df2ddbf812b9479ffa7a64dcaa59a2a9f76"
    assert value.CLOSURE == "179652cb9487163d83c004d358e4d4b49409694c"
    assert value.REPAIR_ZIP_BYTES == 12864
    assert value.REPAIR_ZIP_SHA256 == "2ddb55db15f73738116377de6fb8fa8fba9c5cc2cf23f1f59e2dc112ce63be70"
    assert value.ORIGINAL_HELPER_SHA256 == "4014a80998469607f8a279a4fc7b7abbeff61e349657b7d8224429d142dfa8db"
    assert value.PATCHED_HELPER_SHA256 == "3e6521f6065a3bb61e12b0f2cdcbf1c7f2d40e138269bf85d386aeb2741ab21a"
    assert (value.ORIGINAL_HELPER_BYTES, value.PATCHED_HELPER_BYTES,
        value.INSERT_OFFSET, value.INSERT_BYTES, value.SUFFIX_BYTES) == (
            39623, 39976, 28558, 353, 11065)
    assert value.INSERT_SHA256 == "0fc6d020b99346e159de5496b82f1c5dbd268bae179d1f7934545aaf4511c39e"
    assert (value.COMMAND_MAX_STDOUT, value.COMMAND_MAX_STDERR,
        value.COMMAND_MAX_TIMEOUT_SECONDS) == (65536, 65536, 20)
    assert value.REPAIR_MEMBERS == ("REPAIR.json", "SHA256SUMS", "old_producers.py")


def test_module_has_no_private_path_or_execution_primitive():
    raw = SOURCE.read_text()
    tree = ast.parse(raw)
    strings = [node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    assert not any(text.startswith(("/home/", "/mnt/")) or "Downloads" in text for text in strings)
    imports = {alias.name.split(".")[0] for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if isinstance(node, ast.Import) else [ast.alias(node.module or "")])}
    assert not imports.intersection({"subprocess", "importlib", "runpy"})
    forbidden = {"exec", "eval", "compile", "__import__"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in forbidden for node in ast.walk(tree))


def test_only_four_missing_exec_arrays_are_normalized():
    value = module()
    row = show_row(value, omit=value.EMPTY_EXEC_FIELDS)
    parsed = value.parse_show_output(show_wire([row]), [row["Id"]])[row["Id"]]
    assert all(parsed[name] == "" for name in value.EMPTY_EXEC_FIELDS)
    assert set(parsed) == set(value.SHOW_PROPERTIES)


@pytest.mark.parametrize("field", ("ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost"))
def test_each_missing_or_explicitly_empty_approved_field_is_accepted(field):
    value = module()
    missing = show_row(value, omit=(field,))
    explicit = show_row(value)
    assert value.require_empty_exec_hooks(
        value.parse_show_output(show_wire([missing]), [missing["Id"]])[missing["Id"]])[field] == ""
    assert value.require_empty_exec_hooks(
        value.parse_show_output(show_wire([explicit]), [explicit["Id"]])[explicit["Id"]])[field] == ""


@pytest.mark.parametrize("field", ("ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost"))
def test_nonempty_exec_hook_reaches_unchanged_caller_rejection(field):
    value = module()
    row = show_row(value)
    row[field] = "{ path=/usr/bin/false ; }"
    parsed = value.parse_show_output(show_wire([row]), [row["Id"]])[row["Id"]]
    with pytest.raises(value.PatchContractError, match="EXEC_HOOK_NONEMPTY"):
        value.require_empty_exec_hooks(parsed)


@pytest.mark.parametrize("field", tuple(
    name for name in module().SHOW_PROPERTIES if name not in module().EMPTY_EXEC_FIELDS))
def test_every_other_property_is_never_synthesized_and_caller_access_fails(field):
    value = module()
    row = show_row(value, omit=(field,))
    if field == "Id":
        with pytest.raises(value.PatchContractError, match="UNIT_OUTPUT_IDENTITY"):
            value.parse_show_output(show_wire([row]), ["example.service"])
        return
    parsed = value.parse_show_output(show_wire([row]), ["example.service"])["example.service"]
    assert field not in parsed
    with pytest.raises(KeyError):
        _ = parsed[field]


def test_original_parser_preserves_unrequested_property_without_synthesizing_it():
    value = module()
    row = show_row(value)
    row["ExecReload"] = ""
    parsed = value.parse_show_output(show_wire([row]), [row["Id"]])[row["Id"]]
    assert "ExecReload" in parsed


def test_value_is_split_only_on_first_equals():
    value = module()
    row = show_row(value)
    row["ExecStart"] = "argv=/usr/bin/tool --value=a=b"
    parsed = value.parse_show_output(show_wire([row]), [row["Id"]])
    assert parsed[row["Id"]]["ExecStart"] == row["ExecStart"]


def test_original_duplicate_and_malformed_line_mapping_semantics_are_preserved():
    value = module()
    row = show_row(value)
    valid = show_wire([row]).decode().rstrip("\n")
    duplicate = (valid + "\nMainPID=7\n").encode()
    malformed = (valid + "\nline-without-equals\n").encode()
    assert value.parse_show_output(duplicate, [row["Id"]])[row["Id"]]["MainPID"] == "7"
    assert value.parse_show_output(malformed, [row["Id"]])[row["Id"]]["MainPID"] == "0"


def test_duplicate_or_incomplete_unit_identity_is_rejected():
    value = module()
    first = show_row(value, "first.service")
    duplicate = show_row(value, "first.service")
    with pytest.raises(value.PatchContractError, match="UNIT_OUTPUT_IDENTITY"):
        value.parse_show_output(show_wire([first, duplicate]), ["first.service", "second.service"])
    with pytest.raises(value.PatchContractError, match="UNIT_OUTPUT_INCOMPLETE"):
        value.parse_show_output(show_wire([first]), ["first.service", "second.service"])
    with pytest.raises(value.PatchContractError, match="UNIT_NAME_DUPLICATE"):
        value.parse_show_output(show_wire([first]), ["first.service", "first.service"])


def test_invalid_utf8_and_empty_output_fail_closed():
    value = module()
    with pytest.raises(value.PatchContractError, match="SHOW_UTF8"):
        value.parse_show_output(b"Id=example.service\n\xff\n", ["example.service"])
    with pytest.raises(value.PatchContractError, match="UNIT_OUTPUT_IDENTITY"):
        value.parse_show_output(b"", ["example.service"])


def test_injected_runner_uses_fixed_sixteen_unit_chunks():
    value = module()
    names = [f"unit{number:02d}.service" for number in range(33)]
    calls = []
    def runner(chunk, *, ordinary, max_timeout_seconds, max_stdout, max_stderr):
        calls.append((chunk, ordinary, max_timeout_seconds, max_stdout, max_stderr))
        rows = [show_row(value, name, omit=value.EMPTY_EXEC_FIELDS) for name in chunk]
        return {"returncode": 0, "stdout": show_wire(rows), "stderr": b""}
    rows = value.query_show_rows(runner, names, ordinary=True)
    assert set(rows) == set(names)
    assert [len(call[0]) for call in calls] == [16, 16, 1]
    assert all(call[1:] == (True, 20, 65536, 65536) for call in calls)


def test_empty_unit_list_does_not_call_injected_runner():
    value = module()
    def runner(*_args, **_kwargs):
        pytest.fail("runner called for an empty unit set")
    assert value.query_show_rows(runner, []) == {}


@pytest.mark.parametrize(("response", "reason"), [
    ({"returncode": 1, "stdout": b"", "stderr": b"private failure"}, "SHOW_COMMAND_FAILED"),
    ({"returncode": True, "stdout": b"", "stderr": b""}, "SHOW_RESULT_TYPE"),
    ({"returncode": 0, "stdout": "not bytes", "stderr": b""}, "SHOW_RESULT_TYPE"),
    ({"returncode": 0, "stdout": b"", "stderr": b"", "extra": None}, "SHOW_RESULT"),
])
def test_injected_command_failures_never_reach_parser(response, reason):
    value = module()
    def runner(_chunk, *, ordinary, **_limits):
        assert ordinary is False
        return response
    with pytest.raises(value.PatchContractError, match=reason):
        value.query_show_rows(runner, ["example.service"])


def test_original_command_output_limits_and_nonempty_stderr_are_preserved():
    value = module()
    row = show_row(value)

    def warning(_chunk, **_kwargs):
        return {"returncode": 0, "stdout": show_wire([row]), "stderr": b"warning"}

    assert value.query_show_rows(warning, [row["Id"]])[row["Id"]]["Id"] == row["Id"]
    for key in ("stdout", "stderr"):
        response = {"returncode": 0, "stdout": show_wire([row]), "stderr": b""}
        response[key] = b"x" * 65537

        def oversized(_chunk, **_kwargs):
            return response

        with pytest.raises(value.PatchContractError, match="SHOW_OUTPUT_LIMIT"):
            value.query_show_rows(oversized, [row["Id"]])


def test_injected_runner_exception_is_sanitized():
    value = module()
    def runner(_chunk, **_kwargs):
        raise OSError("private command diagnostic")
    with pytest.raises(value.PatchContractError, match="SHOW_RUNNER_FAILED") as raised:
        value.query_show_rows(runner, ["example.service"])
    assert "private command diagnostic" not in str(raised.value)
    assert raised.value.__cause__ is None


def test_synthetic_archive_verifies_without_returning_private_bytes(synthetic_archive):
    value, original, patched, _repair, _sums, _files, raw = synthetic_archive
    pair = value.verify_helper_pair(original, patched)
    assert pair["change"] == {"kind": "EXACT_INSERTION",
        "offset": value.INSERT_OFFSET, "bytes": value.INSERT_BYTES,
        "sha256": value.INSERT_SHA256}
    assert pair["all_other_helper_bytes_unchanged"] is True
    report = value.verify_repair_zip_bytes(raw)
    assert report["status"] == "OFFLINE_REPAIR_ARCHIVE_PIN_VERIFIED"
    assert report["members"] == list(value.REPAIR_MEMBERS)
    assert report["contains_task_txt"] is False
    assert report["field_execution_authorized"] is False
    assert patched.decode().strip() not in json.dumps(report)
    adoption = value.verify_repair_adoption(original, raw)
    assert adoption["status"] == "OFFLINE_REPAIR_ADOPTION_VERIFIED"
    assert adoption["helper_pair"] == pair
    assert "members" not in adoption and patched.decode().strip() not in json.dumps(adoption)


def test_archive_only_verification_cannot_claim_adoption(synthetic_archive):
    value, original, _patched, *_rest, raw = synthetic_archive
    archive = value.verify_repair_zip_bytes(raw)
    assert "ADOPTION" not in archive["status"]
    with pytest.raises(value.PatchContractError, match="ORIGINAL_HELPER_PIN"):
        value.verify_repair_adoption(original + b"changed", raw)


def test_explicit_path_api_has_no_discovery_and_reads_exact_file(synthetic_archive, tmp_path):
    value, *_rest, raw = synthetic_archive
    target = tmp_path / "caller-selected.zip"
    target.write_bytes(raw)
    target.chmod(0o600)
    assert value.verify_repair_zip_path(target)["archive"]["sha256"] == value.REPAIR_ZIP_SHA256
    alias = tmp_path / "alias.zip"
    alias.symlink_to(target)
    with pytest.raises(value.PatchContractError, match="REPAIR_PATH_OPEN"):
        value.verify_repair_zip_path(alias)


def test_outer_archive_pin_rejects_any_changed_byte(synthetic_archive):
    value, *_rest, raw = synthetic_archive
    changed = raw[:-1] + bytes([raw[-1] ^ 1])
    with pytest.raises(value.PatchContractError, match="REPAIR_ZIP_PIN"):
        value.verify_repair_zip_bytes(changed)


@pytest.mark.parametrize(("mutation", "reason"), [
    ("task", "REPAIR_MEMBERS"),
    ("missing", "REPAIR_MEMBERS"),
    ("mode", "REPAIR_MEMBER_MODE"),
    ("stored", "REPAIR_MEMBER_ENCODING"),
])
def test_inner_archive_contract_rejects_nonexact_members(synthetic_archive, monkeypatch, mutation, reason):
    value, _original, _patched, _repair, _sums, files, _raw = synthetic_archive
    selected, modes, compression = list(files), {}, zipfile.ZIP_DEFLATED
    if mutation == "task":
        selected.append(("TASK.txt", b"must never exist\n"))
    elif mutation == "missing":
        selected.pop()
    elif mutation == "mode":
        modes["old_producers.py"] = 0o644
    else:
        compression = zipfile.ZIP_STORED
    raw = write_zip(selected, modes=modes, compression=compression)
    repin_archive(monkeypatch, value, raw)
    with pytest.raises(value.PatchContractError, match=reason):
        value.verify_repair_zip_bytes(raw)


def test_sha256sums_is_exact_ordered_two_member_contract(synthetic_archive, monkeypatch):
    value, _original, _patched, _repair, sums, _files, _raw = synthetic_archive
    assert value.parse_sha256sums(sums) == {
        "REPAIR.json": value.REPAIR_JSON_SHA256,
        "old_producers.py": value.PATCHED_HELPER_SHA256,
    }
    reversed_rows = b"\n".join(reversed(sums.rstrip(b"\n").splitlines())) + b"\n"
    monkeypatch.setattr(value, "SHA256SUMS_BYTES", len(reversed_rows))
    monkeypatch.setattr(value, "SHA256SUMS_SHA256", hashlib.sha256(reversed_rows).hexdigest())
    with pytest.raises(value.PatchContractError, match="SHA256SUMS_CONTENT"):
        value.parse_sha256sums(reversed_rows)


def test_repair_json_rejects_duplicate_keys_and_semantic_changes(synthetic_archive):
    value, _original, _patched, repair, _sums, _files, _raw = synthetic_archive
    assert value.parse_repair_json(repair)["boundaries"]["contains_task_txt"] is False
    with pytest.raises(value.PatchContractError, match="JSON_DUPLICATE_KEY"):
        value.parse_repair_json(b'{"schema":"one","schema":"two"}')
    changed = value.expected_repair_document()
    changed["boundaries"]["field_execution_authorized"] = True
    with pytest.raises(value.PatchContractError, match="REPAIR_JSON_CONTRACT"):
        value.parse_repair_json(json.dumps(changed).encode())


def test_helper_digest_api_rejects_either_unpinned_input(synthetic_archive):
    value, original, patched, *_rest = synthetic_archive
    with pytest.raises(value.PatchContractError, match="ORIGINAL_HELPER_PIN"):
        value.verify_helper_pair(original + b"changed", patched)
    with pytest.raises(value.PatchContractError, match="PATCHED_HELPER_PIN"):
        value.verify_helper_pair(original, patched + b"changed")


def test_explicit_path_errors_do_not_retain_private_path_in_exception_cause(tmp_path):
    value = module()
    missing = tmp_path / "private-name.zip"
    with pytest.raises(value.PatchContractError, match="REPAIR_PATH_OPEN") as raised:
        value.verify_repair_zip_path(missing)
    assert raised.value.__cause__ is None
