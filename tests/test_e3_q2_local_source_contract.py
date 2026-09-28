"""Synthetic source decoder tests; no private paths or host observation."""
import copy
import json
import os

import pytest

from e3_host import q2_local_source_contract as c


HOST = "/example/source-parent"
CONTROL = "/example/control-parent"
BOOT = "00000000-0000-0000-0000-000000000001"


def raw(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def metadata(path, kind, size):
    return dict(path=path, type=kind, size=size, device=1, inode=2, uid=1000,
        gid=1000, mode=0o700 if kind == "directory" else 0o600, nlink=1,
        atime_ns=1, mtime_ns=1, ctime_ns=1)


def row(path, kind="regular", size=1):
    value = dict(source_path=path, type=kind, source_metadata=metadata(path, kind, size),
        archive_path="synthetic/" + path.rsplit("/", 1)[1], archive_metadata={})
    if kind == "regular":
        value["sha256"] = c.sha(path.encode())
    return value


@pytest.fixture
def sources():
    roots = [HOST + "/history-%02d" % i for i in range(5)]
    rows = [row(root, "directory", 4096) for root in roots]
    rows += [row(roots[i % 5] + "/member-%02d" % i) for i in range(37)]
    rows += [row(HOST + "/sibling-%02d" % i, size=size)
        for i, size in enumerate(c.SIBLING_SIZES)]
    manifest = dict(schema="local-hand-q2-readonly-return-manifest/v1",
        archive="synthetic.tar", archive_bytes=1, archive_sha256="a" * 64,
        entries=rows, entry_count=49, origin="synthetic", regular_file_count=44,
        regular_file_bytes=37 + sum(c.SIBLING_SIZES))
    attestation = dict(schema="local-hand-q2-host-current-attestation/v1", boot_id=BOOT,
        vm_control_files=[dict(path=CONTROL + "/" + name, size=size, sha256=expected,
            uid=1234, inode=999, metadata_stable=False)
            for name, size, expected in c.CONTROL_FILES],
        not_adopted=dict(path="/not/an/inspection/target", command="do-not-execute"))
    carrier = ("HOST_RESULT=" + repr(roots[0]) + "\nHOST_OLD=" + repr(roots[1])
        + "\nraise RuntimeError('source bytes must never execute')\n").encode()
    return [carrier, manifest, attestation]


def derive(monkeypatch, values):
    payloads = [values[0], raw(values[1]), raw(values[2])]
    # Synthetic fixture pins replace constants only in this test process. The
    # production API has no caller-selectable digest, source or path override.
    monkeypatch.setattr(c, "SOURCE_PINS", {
        name: dict(bytes=len(payload), sha256=c.sha(payload))
        for name, payload in zip(("P", "M", "T"), payloads)})
    return c.targets(*payloads)


def test_exact_fixed_authority_source_pins_and_caps():
    assert c.BASELINE == "b8b9ec3da3de43b72e4e17416ea6633494d50c1d"
    assert c.CLOSURE == "8e7545199bde66583e1d643656dece867ab1dbda"
    assert c.SOURCE_PINS == {
        "P": dict(bytes=5426689, sha256="5eef22e497e9e0a867470c6c490336dc80fadd0e506e3419847e6c37b687918b"),
        "M": dict(bytes=50266, sha256="7672ac050609fc7e05481443c9239df0d36f25b4ec9860c2bb833024b962647a"),
        "T": dict(bytes=5913, sha256="76cc2c698dbe882ed246509746bc7088ba55df4199f550af8bad42c9f925dd65"),
    }
    assert c.CONTENT_LIMIT == 10490352
    assert c.READ_LIMIT == c.CONTENT_LIMIT + 11 == 10490363
    assert c.KERNEL_READ_LIMIT == 2 * 65 + 1048577
    assert (c.INPUT_LIMIT, c.OUTPUT_LIMIT, c.REPORT_LIMIT) == (16777216, 2097152, 2080768)


def test_fixed_targets_roles_marker_and_digest_without_field_io(sources, monkeypatch):
    for name in ("open", "stat", "scandir", "listdir"):
        monkeypatch.setattr(os, name, lambda *a, **k: pytest.fail("field I/O"))
    result = derive(monkeypatch, sources)
    selected = result["targets"]
    assert len(selected) == 11
    assert [item["id"] for item in selected] == ["M%02d" % i for i in range(1, 8)] + ["T%02d" % i for i in range(1, 5)]
    assert [item["size_cap"] for item in selected[:7]] == list(c.SIBLING_SIZES)
    assert all(item["source"] == "M" and item["source_role"] == "KNOWN_OBJECT_LOCATOR_ONLY"
        and item["return_raw"] is False for item in selected[:7])
    assert all(item["source"] == "T" and item["source_role"] == "CONTROL_RAW_MATCH_ONLY"
        and item["return_raw"] is True for item in selected[7:])
    assert sum(item["size_cap"] for item in selected) == c.CONTENT_LIMIT
    assert sum(item["size_cap"] for item in selected if item["return_raw"]) == 1684
    assert not any("history-" in item["path"] for item in selected)
    assert result["location"] == dict(host_parent=HOST, control_parent=CONTROL,
        marker_name=c.DIRECTORY_NAME, marker_path=HOST + "/" + c.DIRECTORY_NAME,
        expected_boot_id=BOOT, startup_closure=c.STARTUP_CLOSURE)
    assert c.DIRECTORY_NAME == "q2-startup-window-ff236aad9a4dc238a640080af3364634ca902099bdb2ad7941246dd5fdd99d5f"
    expected = dict(result)
    expected.pop("target_manifest_sha256")
    assert result["target_manifest_sha256"] == c.sha(c.encoded(expected))


@pytest.mark.parametrize("source", ("P", "M", "T"))
@pytest.mark.parametrize("change", ("length", "digest", "type"))
def test_all_source_pins_checked_before_parse(source, change, sources, monkeypatch):
    derive(monkeypatch, sources)
    payloads = [sources[0], raw(sources[1]), raw(sources[2])]
    index = ("P", "M", "T").index(source)
    original = payloads[index]
    payloads[index] = original + b" " if change == "length" else (
        b"!" + original[1:] if change == "digest" else bytearray(original))
    monkeypatch.setattr(c, "_carrier", lambda *a: pytest.fail("parse before every pin checked"))
    with pytest.raises(ValueError, match="LOCAL_SOURCE_" + source + "_PIN"):
        c.targets(*payloads)


@pytest.mark.parametrize("carrier", (
    b'HOST_RESULT="/example/source-parent/history-00"',
    b'HOST_RESULT=str("/example/source-parent/history-00")\nHOST_OLD="/example/source-parent/history-01"',
    b'HOST_RESULT="/example/source-parent/history-00"\nHOST_RESULT="/example/source-parent/history-00"\nHOST_OLD="/example/source-parent/history-01"',
    b'HOST_RESULT="/example/source-parent/history-00"\nHOST_OLD="/example/source-parent/history-00"',
    b'HOST_RESULT="/example/source-parent/history-00"\nHOST_OLD="/other/history-01"',
    b'HOST_RESULT="/example/source-parent/../history-00"\nHOST_OLD="/example/source-parent/history-01"',
    b'HOST_RESULT="/example/source-parent/history-00"\nHOST_OLD="/example/source-parent/history-01"\nif True:\n HOST_RESULT="/other/path"',
    b'HOST_RESULT="/example/source-parent/history-00"\nHOST_OLD="/example/source-parent/history-01"\ndel HOST_RESULT',
    b'HOST_RESULT="/example/source-parent/history-00"\nHOST_OLD="/example/source-parent/history-01"\nHOST_OLD += "/other"',
))
def test_ambiguous_dynamic_aliased_or_reassigned_carrier_rejected(carrier, sources, monkeypatch):
    sources[0] = carrier
    with pytest.raises(ValueError):
        derive(monkeypatch, sources)


@pytest.mark.parametrize("change", ("missing", "extra", "duplicate", "path_mismatch", "type_mismatch",
    "nested_root", "external", "deep_member", "unknown_field", "wrong_size", "boolean_size", "wrong_digest"))
def test_manifest_cannot_expand_or_reinterpret_49_object_locator(change, sources, monkeypatch):
    manifest = sources[1]
    rows = manifest["entries"]
    if change == "missing": rows.pop()
    elif change == "extra": rows.append(row(HOST + "/extra"))
    elif change == "duplicate": rows[-1] = copy.deepcopy(rows[-2])
    elif change == "path_mismatch": rows[-1]["source_metadata"]["path"] = HOST + "/other"
    elif change == "type_mismatch": rows[-1]["source_metadata"]["type"] = "symlink"
    elif change == "nested_root": rows[0] = row(HOST + "/history-01/nested", "directory", 4096)
    elif change == "external": rows[-1] = row("/other/sibling-06", size=c.SIBLING_SIZES[-1])
    elif change == "deep_member": rows[5] = row(HOST + "/history-00/nested/member")
    elif change == "unknown_field": rows[-1]["new_target"] = "/other/path"
    elif change == "wrong_size": rows[-1]["source_metadata"]["size"] += 1
    elif change == "boolean_size": rows[-1]["source_metadata"]["size"] = True
    elif change == "wrong_digest": rows[-1]["sha256"] = "not-a-digest"
    with pytest.raises(ValueError):
        derive(monkeypatch, sources)


def test_manifest_row_order_does_not_change_logical_target_order(sources, monkeypatch):
    first = derive(monkeypatch, sources)
    sources[1]["entries"].reverse()
    second = derive(monkeypatch, sources)
    assert [(x["id"], x["path"], x["size_cap"]) for x in first["targets"]] == [
        (x["id"], x["path"], x["size_cap"]) for x in second["targets"]]
    for item in second["targets"][:7]:
        assert sources[1]["entries"][item["source_index"]]["source_path"] == item["path"]


@pytest.mark.parametrize("change", ("missing", "extra", "duplicate", "private_key", "alias", "other_parent",
    "host_parent", "length", "boolean_length", "digest", "boot", "schema"))
def test_control_selection_cannot_change_raw_targets_or_pins(change, sources, monkeypatch):
    attestation = sources[2]
    rows = attestation["vm_control_files"]
    if change == "missing": rows.pop()
    elif change == "extra": rows.append(dict(path=CONTROL + "/id_ed25519", size=1, sha256="a" * 64))
    elif change == "duplicate": rows[-1] = copy.deepcopy(rows[0])
    elif change == "private_key": rows[-1]["path"] = CONTROL + "/id_ed25519"
    elif change == "alias": rows[-1]["path"] = CONTROL + "/../control-parent/id_ed25519.pub"
    elif change == "other_parent": rows[-1]["path"] = "/other/id_ed25519.pub"
    elif change == "host_parent":
        for item in rows: item["path"] = HOST + "/" + item["path"].rsplit("/", 1)[1]
    elif change == "length": rows[-1]["size"] += 1
    elif change == "boolean_length": rows[-1]["size"] = True
    elif change == "digest": rows[-1]["sha256"] = "f" * 64
    elif change == "boot": attestation["boot_id"] = "invalid"
    elif change == "schema": attestation["schema"] = "other"
    with pytest.raises(ValueError):
        derive(monkeypatch, sources)


def test_unadopted_attestation_metadata_cannot_supply_identity_or_execution(sources, monkeypatch):
    first = derive(monkeypatch, sources)
    for item in sources[2]["vm_control_files"]:
        item.update(uid=0, inode=0, metadata_stable=True)
    sources[2]["not_adopted"] = dict(allow_run=True, uid=0, additional_target="/other/path")
    second = derive(monkeypatch, sources)
    assert first["location"] == second["location"]
    assert first["targets"] == second["targets"]
    assert not any("uid" in item or "metadata_stable" in item for item in second["targets"])


@pytest.mark.parametrize("payload", (b'{"a":1,"a":2}', b'{"a":1.0}', b'{"a":NaN}',
    b'{"a":Infinity}', b'{"a":-1}', b'{"a":9223372036854775808}', b'{"a":"\\ud800"}',
    b'[' * 34 + b'0' + b']' * 34))
def test_strict_json_rejects_ambiguous_or_unbounded_values(payload):
    with pytest.raises(ValueError):
        c.document(payload)


def test_raw_json_duplicate_key_is_rejected_after_matching_test_pin(sources, monkeypatch):
    derive(monkeypatch, sources)
    malformed = raw(sources[2]).rstrip()[:-1] + b',"boot_id":"' + BOOT.encode() + b'"}\n'
    c.SOURCE_PINS["T"] = dict(bytes=len(malformed), sha256=c.sha(malformed))
    with pytest.raises(ValueError, match="DUPLICATE_KEY"):
        c.targets(sources[0], raw(sources[1]), malformed)


def test_no_caller_path_digest_scope_or_action_override(sources, monkeypatch):
    derive(monkeypatch, sources)
    args = [sources[0], raw(sources[1]), raw(sources[2])]
    for key, value in (("paths", []), ("pins", {}), ("scope", "full-run"), ("allow_run", True)):
        with pytest.raises(TypeError):
            c.targets(*args, **{key: value})


def test_canonical_encoding_reports_budget_and_type_failure():
    assert c.document(c.encoded(dict(answer=42))) == dict(answer=42)
    with pytest.raises(ValueError, match="OUTPUT_LIMIT"):
        c.encoded(dict(answer=42), limit=2)
    with pytest.raises(ValueError):
        c.encoded(dict(answer=1.5))
    with pytest.raises(ValueError, match="INPUT_LIMIT"):
        c.document(b"{}", limit=1)
