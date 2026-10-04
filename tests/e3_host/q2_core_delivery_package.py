"""Pure builder/parser for the closed core-delivery ``.lhfp`` format.

No function in this module opens a path, creates an artifact, or invokes a
transport.  Callers must obtain all member bytes through their separately
verified held-descriptor workflow and pass those exact bytes here.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import importlib
from pathlib import Path
import re
import struct
import sys
import types


def _helper():
    spec = importlib.util.spec_from_file_location(
        "_q2_core_delivery_contract", Path(__file__).with_name("q2_core_delivery_contract.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = _helper()


def _approved_module():
    # A private, fixed sibling package supports the validators' relative
    # imports without adding the checkout or candidate to sys.path.
    name = "_q2_core_package_validators"
    directory = str(Path(__file__).parent.resolve())
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [directory]
        sys.modules[name] = package
    c.require(sys.modules[name].__path__ == [directory], "CORE_PACKAGE_VALIDATOR_ORIGIN")
    return importlib.import_module(name + ".q2_core_approved_inputs")


def _validate_approved_raw(raw, *, amendment=None):
    value = c.validate_approved_inputs(c.document(raw, limit=c.APPROVED_INPUTS_LIMIT, newline=True),
                                       amendment=amendment)
    try:
        validated = _approved_module().validate(raw)
    except ValueError as error:
        raise c.ContractError(str(error)) from error
    c.require(validated == value, "CORE_PACKAGE_APPROVED_INPUTS_VALIDATOR")
    return value

MANIFEST_FIELDS = {
    "schema", "scope", "rule", "baseline", "owner_decision", "closure", "implementation",
    "candidate", "wheel", "projection", "entry", "locators", "members", "limits",
    "amendment", "approved_inputs",
}
ENTRY_FIELDS = {
    "loader_path", "loader_bytes", "loader_sha256", "bootstrap_path", "bootstrap_bytes",
    "bootstrap_sha256", "dispatcher_path", "dispatcher_bytes", "dispatcher_sha256",
    "carrier_argv_sha256", "local_management_binding_sha256",
}
LOCATOR_FIELDS = {
    "schema", "observation_record_sha256", "source_relation_sha256", "state_parent",
    "quota_parent", "install_parent", "journal_parent", "evidence_parent", "ordinary_user",
    "ordinary_group", "user_manager_unit", "query_parent_unit", "controller_parent_unit",
    "management_parent_unit", "supervisor_parent_unit", "ordinary_parent_unit",
    "retained_ordinary_parent_path", "carrier_unit",
}
MEMBER_FIELDS = {"path", "role", "mode", "bytes", "sha256", "origin"}
ROLES = {
    "candidate-worktree", "candidate-git-metadata", "wheel", "projection", "field-code", "approved-inputs",
}
FIELD_PATHS = ("field/loader.py", "field/bootstrap.py", "field/dispatcher.py")
FIELD_LIMITS = {
    "field/loader.py": 8192,
    "field/bootstrap.py": 49152,
    "field/dispatcher.py": 262144,
}


def _git_blob(raw):
    c.require(type(raw) is bytes, "CORE_PACKAGE_MEMBER_BYTES")
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def member(path, role, mode, raw, origin):
    c.relative_path(path, "CORE_PACKAGE_MEMBER_PATH")
    c.require(role in ROLES and mode in ((0o600,) if role == "approved-inputs" else (0o644, 0o755))
              and type(raw) is bytes
              and len(raw) <= c.PACKAGE_LIMITS["member_bytes"], "CORE_PACKAGE_MEMBER")
    return {
        "path": path, "role": role, "mode": mode, "bytes": len(raw),
        "sha256": c.sha256(raw), "origin": copy.deepcopy(origin),
    }


def approved_input_member(raw, *, amendment=None):
    value = _validate_approved_raw(raw, amendment=amendment)
    header = {"path": c.APPROVED_INPUTS_PATH, "bytes": len(raw), "sha256": c.sha256(raw),
              "approved_source_relation_sha256": c.sha256(c.canonical(value["source_relation"]))}
    origin = {"kind": "approved-inputs", **{key: item for key, item in header.items() if key != "path"}}
    return member(c.APPROVED_INPUTS_PATH, "approved-inputs", 0o600, raw, origin), header


def field_member_blobs(loader, bootstrap, dispatcher, *, implementation_commit,
                       source_paths=None):
    """Return exact field member records and their bytes without writing them."""
    c.commit(implementation_commit, "CORE_PACKAGE_IMPLEMENTATION")
    blobs = dict(zip(FIELD_PATHS, (loader, bootstrap, dispatcher), strict=True))
    source_paths = source_paths or {
        "field/loader.py": "tests/e3_host/q2_core_delivery_loader.py",
        "field/bootstrap.py": "tests/e3_host/q2_core_delivery_bootstrap.py",
        "field/dispatcher.py": "tests/e3_host/q2_core_delivery_dispatcher.py",
    }
    c.require(set(source_paths) == set(FIELD_PATHS), "CORE_PACKAGE_FIELD_SOURCES")
    rows = []
    for path in FIELD_PATHS:
        raw = blobs[path]
        c.require(type(raw) is bytes and 0 < len(raw) <= FIELD_LIMITS[path],
                  "CORE_PACKAGE_FIELD_LIMIT")
        source = source_paths[path]
        c.relative_path(source, "CORE_PACKAGE_FIELD_SOURCE")
        rows.append(member(path, "field-code", 0o644, raw, {
            "kind": "implementation-blob", "commit": implementation_commit,
            "path": source, "blob": _git_blob(raw),
        }))
    return rows, blobs


def locator_relation(locators, local_management_binding_sha256):
    c.digest(local_management_binding_sha256, "CORE_PACKAGE_MANAGEMENT_BINDING")
    c.require(type(locators) is dict and set(locators) == LOCATOR_FIELDS,
              "CORE_PACKAGE_LOCATOR_FIELDS")
    relation_locators = {key: copy.deepcopy(value) for key, value in locators.items()
                         if key != "source_relation_sha256"}
    return {
        "schema": c.LOCATOR_RELATION_SCHEMA,
        "local_management_binding_sha256": local_management_binding_sha256,
        "observation_record_sha256": locators["observation_record_sha256"],
        "locators": relation_locators,
    }


def validate_locators(value, local_management_binding_sha256):
    c.exact(value, LOCATOR_FIELDS, "CORE_PACKAGE_LOCATOR_FIELDS")
    c.require(value["schema"] == c.LOCATORS_SCHEMA and value["carrier_unit"] == c.CARRIER_UNIT,
              "CORE_PACKAGE_LOCATOR_AUTHORITY")
    for key in ("observation_record_sha256", "source_relation_sha256"):
        c.digest(value[key], "CORE_PACKAGE_LOCATOR_DIGEST")
    for key in ("state_parent", "quota_parent", "install_parent", "journal_parent",
                "evidence_parent", "retained_ordinary_parent_path"):
        c.absolute_path(value[key], "CORE_PACKAGE_LOCATOR_PATH")
    c.require(len({value[key] for key in ("state_parent", "quota_parent", "install_parent",
                                          "journal_parent", "evidence_parent")}) == 5,
              "CORE_PACKAGE_LOCATOR_ALIAS")
    for key in ("ordinary_user", "ordinary_group"):
        c.require(type(value[key]) is str and re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", value[key]),
                  "CORE_PACKAGE_LOCATOR_ACCOUNT")
    for key in ("user_manager_unit", "query_parent_unit", "controller_parent_unit",
                "management_parent_unit", "supervisor_parent_unit", "ordinary_parent_unit",
                "carrier_unit"):
        c.require(type(value[key]) is str and value[key].isascii() and 1 <= len(value[key]) <= 255
                  and re.fullmatch(r"[A-Za-z0-9_.@:-]+", value[key]),
                  "CORE_PACKAGE_LOCATOR_UNIT")
    relation = locator_relation(value, local_management_binding_sha256)
    expected = c.sha256(c.canonical(relation))
    c.require(value["source_relation_sha256"] == expected, "CORE_PACKAGE_LOCATOR_RELATION")
    return value


def _validate_origin(item):
    role, origin = item["role"], item["origin"]
    c.require(type(origin) is dict, "CORE_PACKAGE_ORIGIN")
    if role in ("candidate-worktree", "field-code"):
        c.exact(origin, {"kind", "commit", "path", "blob"}, "CORE_PACKAGE_ORIGIN")
        expected_kind = "candidate-blob" if role == "candidate-worktree" else "implementation-blob"
        expected_commit = c.CANDIDATE["commit"] if role == "candidate-worktree" else None
        c.require(origin["kind"] == expected_kind, "CORE_PACKAGE_ORIGIN")
        c.commit(origin["commit"], "CORE_PACKAGE_ORIGIN")
        if expected_commit is not None:
            c.require(origin["commit"] == expected_commit, "CORE_PACKAGE_ORIGIN")
        c.relative_path(origin["path"], "CORE_PACKAGE_ORIGIN")
        c.require(re.fullmatch(r"[0-9a-f]{40}", origin["blob"] or ""), "CORE_PACKAGE_ORIGIN")
    elif role == "candidate-git-metadata":
        c.exact(origin, {"kind", "commit", "git_path"}, "CORE_PACKAGE_ORIGIN")
        c.require(origin["kind"] == "candidate-git-metadata"
                  and origin["commit"] == c.CANDIDATE["commit"], "CORE_PACKAGE_ORIGIN")
        c.relative_path(origin["git_path"], "CORE_PACKAGE_ORIGIN")
        c.require(origin["git_path"].startswith(".git/"), "CORE_PACKAGE_ORIGIN")
    elif role == "approved-inputs":
        c.exact(origin, {"kind", "bytes", "sha256", "approved_source_relation_sha256"},
                "CORE_PACKAGE_ORIGIN")
        c.require(origin["kind"] == role and origin["bytes"] == item["bytes"]
                  and origin["sha256"] == item["sha256"], "CORE_PACKAGE_ORIGIN")
        c.digest(origin["approved_source_relation_sha256"], "CORE_PACKAGE_ORIGIN")
    else:
        c.exact(origin, {"kind", "basename", "sha256"}, "CORE_PACKAGE_ORIGIN")
        expected = c.WHEEL if role == "wheel" else c.PROJECTION
        c.require(origin["kind"] == role and origin["basename"] == expected["basename"]
                  and origin["sha256"] == expected["sha256"], "CORE_PACKAGE_ORIGIN")
    return origin


def validate_member(item):
    c.exact(item, MEMBER_FIELDS, "CORE_PACKAGE_MEMBER_FIELDS")
    path = c.relative_path(item["path"], "CORE_PACKAGE_MEMBER_PATH")
    c.require(item["role"] in ROLES and type(item["mode"]) is int
              and item["mode"] in ((0o600,) if item["role"] == "approved-inputs" else (0o644, 0o755)),
              "CORE_PACKAGE_MEMBER")
    c.integer(item["bytes"], 0, c.PACKAGE_LIMITS["member_bytes"], "CORE_PACKAGE_MEMBER")
    c.digest(item["sha256"], "CORE_PACKAGE_MEMBER")
    _validate_origin(item)
    role = item["role"]
    if role == "candidate-worktree":
        c.require(path.startswith("candidate/") and not path.startswith("candidate/.git/")
                  and path == "candidate/" + item["origin"]["path"], "CORE_PACKAGE_MEMBER_PATH")
    elif role == "candidate-git-metadata":
        c.require(path.startswith("candidate/.git/")
                  and path == "candidate/" + item["origin"]["git_path"], "CORE_PACKAGE_MEMBER_PATH")
    elif role == "wheel":
        c.require(path == "artifacts/" + c.WHEEL["basename"]
                  and item["bytes"] == c.WHEEL["bytes"] and item["sha256"] == c.WHEEL["sha256"],
                  "CORE_PACKAGE_WHEEL")
    elif role == "projection":
        c.require(path == "artifacts/" + c.PROJECTION["basename"]
                  and item["bytes"] == c.PROJECTION["bytes"]
                  and item["sha256"] == c.PROJECTION["sha256"], "CORE_PACKAGE_PROJECTION")
    elif role == "approved-inputs":
        c.require(path == c.APPROVED_INPUTS_PATH and 0 < item["bytes"] <= c.APPROVED_INPUTS_LIMIT,
                  "CORE_PACKAGE_APPROVED_INPUTS")
    else:
        c.require(path in FIELD_PATHS and item["bytes"] <= FIELD_LIMITS[path],
                  "CORE_PACKAGE_FIELD")
    return item


def validate_manifest(value):
    c.exact(value, MANIFEST_FIELDS, "CORE_PACKAGE_MANIFEST_FIELDS")
    c.require(value["schema"] == c.PACKAGE_SCHEMA and value["scope"] == c.SCOPE,
              "CORE_PACKAGE_AUTHORITY")
    c.require(value["rule"] == c.RULE and value["baseline"] == c.BASELINE
              and value["owner_decision"] == c.OWNER_DECISION and value["closure"] == c.CLOSURE
              and value["candidate"] == c.CANDIDATE and value["wheel"] == c.WHEEL
              and value["projection"] == c.PROJECTION and value["limits"] == c.PACKAGE_LIMITS,
              "CORE_PACKAGE_AUTHORITY")
    c.exact(value["implementation"], {"commit", "tree"}, "CORE_PACKAGE_IMPLEMENTATION")
    for key in ("commit", "tree"):
        c.commit(value["implementation"][key], "CORE_PACKAGE_IMPLEMENTATION")
    c.require(value["implementation"] != c.CLOSURE, "CORE_PACKAGE_IMPLEMENTATION")
    c.validate_amendment(value["amendment"], implementation=value["implementation"])
    approved = c.exact(value["approved_inputs"],
        {"path", "bytes", "sha256", "approved_source_relation_sha256"}, "CORE_PACKAGE_APPROVED_FIELDS")
    c.require(approved["path"] == c.APPROVED_INPUTS_PATH, "CORE_PACKAGE_APPROVED_INPUTS")
    c.integer(approved["bytes"], 1, c.APPROVED_INPUTS_LIMIT, "CORE_PACKAGE_APPROVED_INPUTS")
    for key in ("sha256", "approved_source_relation_sha256"):
        c.digest(approved[key], "CORE_PACKAGE_APPROVED_INPUTS")
    entry = c.exact(value["entry"], ENTRY_FIELDS, "CORE_PACKAGE_ENTRY_FIELDS")
    expected_paths = {"loader": "field/loader.py", "bootstrap": "field/bootstrap.py",
                      "dispatcher": "field/dispatcher.py"}
    for name, path in expected_paths.items():
        c.require(entry[name + "_path"] == path, "CORE_PACKAGE_ENTRY_PATH")
        c.integer(entry[name + "_bytes"], 1, FIELD_LIMITS[path], "CORE_PACKAGE_ENTRY_LIMIT")
        c.digest(entry[name + "_sha256"], "CORE_PACKAGE_ENTRY_DIGEST")
    for key in ("carrier_argv_sha256", "local_management_binding_sha256"):
        c.digest(entry[key], "CORE_PACKAGE_ENTRY_DIGEST")
    validate_locators(value["locators"], entry["local_management_binding_sha256"])
    members = value["members"]
    c.require(type(members) is list and 1 <= len(members) <= c.PACKAGE_LIMITS["members"],
              "CORE_PACKAGE_MEMBER_COUNT")
    paths = []
    for item in members:
        validate_member(item); paths.append(item["path"])
    c.require(paths == sorted(paths, key=lambda item: item.encode("ascii"))
              and len(paths) == len(set(paths)), "CORE_PACKAGE_MEMBER_ORDER")
    by_role = {role: [item for item in members if item["role"] == role] for role in ROLES}
    c.require(by_role["candidate-worktree"] and by_role["candidate-git-metadata"]
              and len(by_role["wheel"]) == len(by_role["projection"]) == len(by_role["approved-inputs"]) == 1
              and {item["path"] for item in by_role["field-code"]} == set(FIELD_PATHS)
              and len(by_role["field-code"]) == 3, "CORE_PACKAGE_INVENTORY")
    approved_row = by_role["approved-inputs"][0]
    c.require(all(approved_row[key] == approved[key] for key in ("path", "bytes", "sha256"))
              and approved_row["origin"] == {"kind": "approved-inputs", **{
                  key: item for key, item in approved.items() if key != "path"}}, "CORE_PACKAGE_APPROVED_BINDING")
    for name, path in expected_paths.items():
        row = next(item for item in by_role["field-code"] if item["path"] == path)
        c.require((row["bytes"], row["sha256"], row["origin"]["commit"])
                  == (entry[name + "_bytes"], entry[name + "_sha256"],
                      value["implementation"]["commit"]), "CORE_PACKAGE_ENTRY_BINDING")
    return value


def make_manifest(*, implementation, amendment, approved_inputs, entry, locators, members):
    value = {
        "schema": c.PACKAGE_SCHEMA, "scope": c.SCOPE, "rule": copy.deepcopy(c.RULE),
        "baseline": copy.deepcopy(c.BASELINE), "owner_decision": copy.deepcopy(c.OWNER_DECISION),
        "closure": copy.deepcopy(c.CLOSURE), "implementation": copy.deepcopy(implementation),
        "amendment": copy.deepcopy(amendment), "approved_inputs": copy.deepcopy(approved_inputs),
        "candidate": copy.deepcopy(c.CANDIDATE), "wheel": copy.deepcopy(c.WHEEL),
        "projection": copy.deepcopy(c.PROJECTION), "entry": copy.deepcopy(entry),
        "locators": copy.deepcopy(locators),
        "members": sorted(copy.deepcopy(members), key=lambda item: item["path"].encode("ascii")),
        "limits": copy.deepcopy(c.PACKAGE_LIMITS),
    }
    return validate_manifest(value)


def _validate_approved_member(manifest, raw):
    value = _validate_approved_raw(raw, amendment=manifest["amendment"])
    expected = manifest["approved_inputs"]
    c.require(len(raw) == expected["bytes"] and c.sha256(raw) == expected["sha256"]
              and c.sha256(c.canonical(value["source_relation"]))
                  == expected["approved_source_relation_sha256"], "CORE_PACKAGE_APPROVED_BINDING")


def build_package(manifest, member_bytes):
    validate_manifest(manifest)
    c.require(type(member_bytes) is dict and set(member_bytes) == {item["path"] for item in manifest["members"]},
              "CORE_PACKAGE_MEMBER_SET")
    raw_manifest = c.canonical(manifest, newline=True, limit=c.PACKAGE_LIMITS["manifest_bytes"])
    body = bytearray()
    for item in manifest["members"]:
        raw = member_bytes[item["path"]]
        c.require(type(raw) is bytes and len(raw) == item["bytes"]
                  and c.sha256(raw) == item["sha256"], "CORE_PACKAGE_MEMBER_BYTES")
        if item["role"] in ("candidate-worktree", "field-code"):
            c.require(item["origin"]["blob"] == _git_blob(raw), "CORE_PACKAGE_MEMBER_BLOB")
        if item["role"] == "approved-inputs":
            _validate_approved_member(manifest, raw)
        body.extend(raw)
        c.require(len(body) <= c.PACKAGE_LIMITS["package_bytes"], "CORE_PACKAGE_LIMIT")
    result = c.PACKAGE_MAGIC + struct.pack(">Q", len(raw_manifest)) + raw_manifest + bytes(body)
    c.require(len(result) <= c.PACKAGE_LIMITS["package_bytes"], "CORE_PACKAGE_LIMIT")
    return result


def parse_package(raw):
    c.require(type(raw) is bytes and 16 < len(raw) <= c.PACKAGE_LIMITS["package_bytes"]
              and raw.startswith(c.PACKAGE_MAGIC), "CORE_PACKAGE_FRAME")
    offset = len(c.PACKAGE_MAGIC)
    c.require(len(raw) >= offset + 8, "CORE_PACKAGE_FRAME")
    length = struct.unpack(">Q", raw[offset:offset + 8])[0]; offset += 8
    c.require(0 < length <= c.PACKAGE_LIMITS["manifest_bytes"] and offset + length <= len(raw),
              "CORE_PACKAGE_MANIFEST_LIMIT")
    manifest_raw = raw[offset:offset + length]; offset += length
    manifest = c.document(manifest_raw, limit=c.PACKAGE_LIMITS["manifest_bytes"], newline=True)
    validate_manifest(manifest)
    members = {}
    for item in manifest["members"]:
        end = offset + item["bytes"]
        c.require(end <= len(raw), "CORE_PACKAGE_TRUNCATED")
        content = raw[offset:end]; offset = end
        c.require(c.sha256(content) == item["sha256"], "CORE_PACKAGE_MEMBER_DIGEST")
        if item["role"] in ("candidate-worktree", "field-code"):
            c.require(item["origin"]["blob"] == _git_blob(content), "CORE_PACKAGE_MEMBER_BLOB")
        if item["role"] == "approved-inputs":
            _validate_approved_member(manifest, content)
        members[item["path"]] = content
    c.require(offset == len(raw), "CORE_PACKAGE_TRAILING_BYTES")
    return manifest, members
