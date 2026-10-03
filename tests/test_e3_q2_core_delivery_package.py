import copy
import hashlib
import struct

import pytest

from e3_host import q2_core_delivery_package as p


IMPLEMENTATION = {"commit": "b" * 40, "tree": "c" * 40}


def fixture(monkeypatch):
    wheel = b"unit-wheel"
    projection = b'{"schema":"unit-projection"}\n'
    monkeypatch.setattr(p.c, "WHEEL", {
        "basename": "infra_local_hand-0.2.0a1-py3-none-any.whl", "bytes": len(wheel),
        "sha256": hashlib.sha256(wheel).hexdigest(), "payload_digest": "d" * 64})
    monkeypatch.setattr(p.c, "PROJECTION", {
        "basename": ".local-hand-source-projection.json", "bytes": len(projection),
        "sha256": hashlib.sha256(projection).hexdigest(), "file_count": 1})
    loader = b"LOADER"
    bootstrap = b"BOOTSTRAP"
    dispatcher = b"class FieldEffects: pass\ndef dispatch(context,effects): return b''\n"
    fields, field_bytes = p.field_member_blobs(
        loader, bootstrap, dispatcher, implementation_commit=IMPLEMENTATION["commit"])
    # The frozen candidate contains tracked empty files; zero-byte regular
    # members are valid and still bind their Git blob and SHA-256 identities.
    worktree = b""
    git_head = b"ref: refs/heads/detached\n"
    rows = [
        p.member("candidate/README.md", "candidate-worktree", 0o644, worktree,
                 {"kind": "candidate-blob", "commit": p.c.CANDIDATE["commit"],
                  "path": "README.md", "blob": p._git_blob(worktree)}),
        p.member("candidate/.git/HEAD", "candidate-git-metadata", 0o644, git_head,
                 {"kind": "candidate-git-metadata", "commit": p.c.CANDIDATE["commit"],
                  "git_path": ".git/HEAD"}),
        p.member("artifacts/" + p.c.WHEEL["basename"], "wheel", 0o644, wheel,
                 {"kind": "wheel", "basename": p.c.WHEEL["basename"],
                  "sha256": p.c.WHEEL["sha256"]}),
        p.member("artifacts/" + p.c.PROJECTION["basename"], "projection", 0o644, projection,
                 {"kind": "projection", "basename": p.c.PROJECTION["basename"],
                  "sha256": p.c.PROJECTION["sha256"]}),
        *fields,
    ]
    raw_by_path = {
        "candidate/README.md": worktree, "candidate/.git/HEAD": git_head,
        "artifacts/" + p.c.WHEEL["basename"]: wheel,
        "artifacts/" + p.c.PROJECTION["basename"]: projection, **field_bytes,
    }
    by_path = {row["path"]: row for row in rows}
    management = "e" * 64
    entry = {
        "loader_path": "field/loader.py", "loader_bytes": len(loader),
        "loader_sha256": hashlib.sha256(loader).hexdigest(),
        "bootstrap_path": "field/bootstrap.py", "bootstrap_bytes": len(bootstrap),
        "bootstrap_sha256": hashlib.sha256(bootstrap).hexdigest(),
        "dispatcher_path": "field/dispatcher.py", "dispatcher_bytes": len(dispatcher),
        "dispatcher_sha256": hashlib.sha256(dispatcher).hexdigest(),
        "carrier_argv_sha256": "f" * 64, "management_entry_binding_sha256": management,
    }
    locators = {
        "schema": p.c.LOCATORS_SCHEMA, "observation_record_sha256": "1" * 64,
        "source_relation_sha256": "0" * 64,
        "state_parent": "/fixture/state", "quota_parent": "/fixture/quota",
        "install_parent": "/fixture/install", "journal_parent": "/fixture/journal",
        "evidence_parent": "/fixture/evidence", "ordinary_user": "q2job",
        "ordinary_group": "q2job", "user_manager_unit": "user@1100.service",
        "query_parent_unit": "lhq-query.slice", "controller_parent_unit": "lhq-controller.slice",
        "management_parent_unit": "lhq-management.slice",
        "supervisor_parent_unit": "lhq-supervisor.slice",
        "ordinary_parent_unit": "lhq-ordinary.slice",
        "retained_ordinary_parent_path": "/system.slice/lhq-retained.slice",
        "carrier_unit": p.c.CARRIER_UNIT,
    }
    locators["source_relation_sha256"] = p.c.sha256(p.c.canonical(
        p.locator_relation(locators, management), newline=True))
    manifest = p.make_manifest(implementation=IMPLEMENTATION, entry=entry,
                               locators=locators, members=rows)
    return manifest, raw_by_path


def test_field_blob_mapping_is_exact_and_bounded(monkeypatch):
    manifest, raw = fixture(monkeypatch)
    fields = [item for item in manifest["members"] if item["role"] == "field-code"]
    assert [item["path"] for item in fields] == sorted(p.FIELD_PATHS)
    assert all(item["origin"]["kind"] == "implementation-blob" for item in fields)
    assert all(item["origin"]["commit"] == IMPLEMENTATION["commit"] for item in fields)
    assert all(item["origin"]["blob"] == p._git_blob(raw[item["path"]]) for item in fields)


def test_package_round_trip_has_one_manifest_and_exact_member_closure(monkeypatch):
    manifest, members = fixture(monkeypatch)
    raw = p.build_package(manifest, members)
    parsed, parsed_members = p.parse_package(raw)
    assert parsed == manifest
    assert parsed_members == members
    assert parsed_members["candidate/README.md"] == b""
    assert raw.startswith(p.c.PACKAGE_MAGIC)
    length = struct.unpack(">Q", raw[len(p.c.PACKAGE_MAGIC):len(p.c.PACKAGE_MAGIC) + 8])[0]
    assert raw[len(p.c.PACKAGE_MAGIC) + 8:len(p.c.PACKAGE_MAGIC) + 8 + length].endswith(b"\n")
    assert len(raw) <= p.c.PACKAGE_LIMITS["package_bytes"]


def test_package_rejects_mutated_truncated_trailing_or_unlisted_member(monkeypatch):
    manifest, members = fixture(monkeypatch)
    raw = p.build_package(manifest, members)
    with pytest.raises(p.c.ContractError, match="CORE_PACKAGE_MEMBER_DIGEST"):
        changed = bytearray(raw); changed[-1] ^= 1
        p.parse_package(bytes(changed))
    with pytest.raises(p.c.ContractError, match="CORE_PACKAGE_TRUNCATED"):
        p.parse_package(raw[:-1])
    with pytest.raises(p.c.ContractError, match="CORE_PACKAGE_TRAILING_BYTES"):
        p.parse_package(raw + b"x")
    with pytest.raises(p.c.ContractError, match="CORE_PACKAGE_MEMBER_SET"):
        p.build_package(manifest, dict(members, extra=b"x"))


def test_manifest_rejects_open_schema_origin_and_locator_relation(monkeypatch):
    manifest, members = fixture(monkeypatch)
    changed = copy.deepcopy(manifest); changed["extra"] = None
    with pytest.raises(p.c.ContractError, match="CORE_PACKAGE_MANIFEST_FIELDS"):
        p.validate_manifest(changed)
    changed = copy.deepcopy(manifest)
    row = next(item for item in changed["members"] if item["role"] == "candidate-worktree")
    row["origin"]["commit"] = "a" * 40
    with pytest.raises(p.c.ContractError, match="CORE_PACKAGE_ORIGIN"):
        p.validate_manifest(changed)
    changed = copy.deepcopy(manifest); changed["locators"]["source_relation_sha256"] = "9" * 64
    with pytest.raises(p.c.ContractError, match="CORE_PACKAGE_LOCATOR_RELATION"):
        p.validate_manifest(changed)


def test_package_rejects_entry_member_drift_and_non_ascii_path(monkeypatch):
    manifest, members = fixture(monkeypatch)
    changed = copy.deepcopy(manifest); changed["entry"]["loader_sha256"] = "7" * 64
    with pytest.raises(p.c.ContractError, match="CORE_PACKAGE_ENTRY_BINDING"):
        p.validate_manifest(changed)
    with pytest.raises(p.c.ContractError, match="CORE_PACKAGE_MEMBER_PATH"):
        p.member("field/加载.py", "field-code", 0o644, b"x", {})
