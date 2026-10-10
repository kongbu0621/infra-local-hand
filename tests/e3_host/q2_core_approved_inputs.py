"""Source-bound approved inputs for the closed core amendment.

``build`` consumes held raw bytes, never caller-approved rows. ``validate``
independently checks the canonical artifact's fixed pins, rows and relations;
passing ``sources`` additionally replays the retained-source derivation. Neither
API observes a guest, writes files, issues a request or establishes live admission.
The no-sources parser is deliberately not a raw-source verification certificate.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import io
import re
from pathlib import PurePosixPath
import shlex
import stat
import tarfile

from . import q2_core_delivery_contract as c
from . import q2_core_legacy_inputs as legacy
from . import q2_core_obligation_inputs as horizon
from . import q2_core_policy_basis as policy
from . import q2_core_prior_attempt as prior_attempt


SCHEMA = "local-hand-q2-core-approved-inputs/v1"
LIMIT = 1048576
FIELDS = {"schema", "scope", "amendment", "source_relation", "policy_basis",
          "historical_capacity_obligations", "retained_preparation", "reconciliation"}
LOCATOR_CARRIERS = (
    ("collection_capture", 1835, "56c29ed9ffe2cf79235baca6b000afaec9ae84b51b2356c664e44d6b34a4fb18"),
    ("guest_raw", 20164157, "078b4a5bc198caa42760c31d2a4f8d0be1dd3564090ea316c799bfe6d9e653f7"),
    ("guest_manifest", 3419814, "82c8c13e250ac0be0957b766e84827514dd50cc5cc53d461c126d6dd0523f735"),
    ("guest_inventory", 922584, "0b1f337f219d3b8d06f2d2a22fc30d2d034afef40decfa7db26051c0ea009a62"),
)
LOCATOR_MEMBERS = (
    ("original_plan", "root/q2-transfer-20260926a/plan.json", 9814,
     "efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c"),
    ("retry_preparation", "root/q2-retry-setup-20260927a/retry-preparation.json", 61119,
     "586f0fd79ceb869a8e1ed238d925b6cdbf2cceaddf233687df81ea320bded4fb"),
)
LOCATOR_MAPPINGS = (
    ("state_parent", "original_plan", "/directories/state/path", "dirname"),
    ("quota_parent", "original_plan", "/mounts/quota/path", "identity"),
    ("install_parent", "original_plan", "/candidate/destination", "dirname"),
    ("journal_parent", "original_plan", "/mounts/journal/path", "identity"),
    ("evidence_parent", "original_plan", "/mounts/evidence/path", "identity"),
    ("ordinary_user", "original_plan", "/account/name", "identity"),
    ("ordinary_group", "original_plan", "/account/name", "identity"),
    ("user_manager_unit", "retry_preparation", "/facts/parents/manager/unit", "identity"),
    ("query_parent_unit", "original_plan", "/parents/query/unit", "identity"),
    ("controller_parent_unit", "original_plan", "/parents/controller/unit", "identity"),
    ("management_parent_unit", "original_plan", "/parents/management/unit", "identity"),
    ("supervisor_parent_unit", "original_plan", "/parents/supervisor/unit", "identity"),
    ("ordinary_parent_unit", "original_plan", "/parents/ordinary/unit", "identity"),
    ("retained_ordinary_parent_path", "retry_preparation", "/facts/parents/ordinary/path", "identity"),
    ("retained_paths", "original_plan", "/retained", "source_order_identity_array"),
    ("retained_domains", "original_plan", "/retained_domains", "source_order_identity_array"),
)
LATER_REVIEWS = (
    ("LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1", "20261002a",
     "docs/a2-execution/Q2_OLD_PRODUCER_ADMISSION_RETRY_IMPLEMENTATION_REVIEW.md",
     "de276883d2a0b1a68009ef994bf24211ac0adb4fe5a5053da70c349e241c7d9d"),
    ("LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1", "namespace_delivery",
     "docs/a2-execution/Q2_NAMESPACE_FIXTURE_DELIVERY_IMPLEMENTATION_REVIEW.md",
     "bd5d530652380777bca60905b11ef56caa760c794fee611748ae7c4f1aee5026"),
    ("LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1", "core_20261003a",
     "docs/a2-execution/Q2_CORE_ACCEPTANCE_DELIVERY_IMPLEMENTATION_REVIEW.md",
     "e64f1be1287ac8bed5f582b01e179b66dd79ead0eb91e8ccf1c71d3ea0095da0"),
)
LEGACY_BLOBS = dict(startup_retry="8057e5c34c228b456a7ebbb1a1c06c631e499328",
    reconciliation_sources="b5f904ee7053836be5f57d5e72574fa86f73d97a",
    reconciliation_billing="46f753e39f0185698f105dbf5b2a48941c2cfa42")
ADOPTED_RAW = (
    ("second-bootstrap-intent", 556, "58992ee2ff0d66fec5e10c7e138e8de4529089ca35d76f71200db1a05ac160b6"),
    ("second-bootstrap-attestation", 7766, "cfc6c07265b4edc6d0b26e67a6ca9cfc19c652b4d011a2386b9bd95e945a34cb"),
)
RETAINED_PINS = dict(paths=(1196, "1ea38f024d0ed06ec5d801ac9fc1b99f4938366d3cc979d8f5ba3b9eddd013c6"),
    domains=(267, "45c231e6f4dd1360888b9e4e3f790ce175440b8af89231801feeede2b21a2c4c"),
    object=(1484, "24772cefec5e2c51364a1f4d1dadf692a2a666999077772138201004f811a808"))
PRODUCER_SHA256 = "f2f4b57b4a34bbfabe483b20865275246cdf35d3497a1c24b375deb7a508ae1b"
RECONCILIATION = dict(state="NO_ELIGIBLE_RETAINED_SEALED_RECORD_SOURCE", applied=[],
    released_bytes=0, released_inodes=0,
    record_basenames=["evidence-adoption.json", "reconciliation-intent.json", "live-attestation.json",
                      "reconciliation-record.json", "reconciliation-seal.json"])


@dataclass(frozen=True)
class ApprovedInputSources:
    """Already held raw closure; no paths or callable validation substitutes.

    Tokens are the frozen fixed carrier array derived from verified D blobs by
    the package builder. This component binds their bytes; the package builder
    must independently reconstruct them from those same implementation blobs.
    ``historical_tools`` is the exact 42-file legacy source closure, basename
    keys, obtained from legacy D. The retained frame restores its pinned input.
    """
    amendment: dict
    locator_carriers: dict
    horizon_archives: dict
    legacy_frame: bytes
    historical_tools: dict
    policy_sources: dict
    remote_tokens: list
    later_reviews: dict
    producer_raw: bytes
    prior_core_files: dict
    prior_diagnostic_files: dict
    journal_files: dict
    journal_sources: dict
    journal_frozen: dict


def _require(ok, code):
    c.require(ok, "CORE_APPROVED_INPUTS_" + code)


def _hash(value):
    return c.sha256(c.canonical(value))


def _equal(value, expected, code):
    _require(c.canonical(value) == c.canonical(expected), code)


def _pin(raw, size, digest, code):
    _require(type(raw) is bytes and len(raw) == size and c.sha256(raw) == digest, code)


def _vector(value, pin, code):
    _pin(c.canonical(value), *pin, code)


def _locator_relation():
    return dict(schema="local-hand-q2-core-locator-source-relation/v1", historical_only=True,
        carriers=[dict(role=role, bytes=size, sha256=digest) for role, size, digest in LOCATOR_CARRIERS],
        members=[dict(role=role, carrier_role="guest_raw", path=path, bytes=size, sha256=digest)
                 for role, path, size, digest in LOCATOR_MEMBERS],
        mappings=[dict(role=role, source_role=source, pointer=pointer, transform=transform)
                  for role, source, pointer, transform in LOCATOR_MAPPINGS], zero_mismatch=True)


def _later_relation():
    return [dict(scope=scope, batch=batch, state="NOT_ISSUED", evidence=dict(path=path, sha256=pin))
            for scope, batch, path, pin in LATER_REVIEWS]


def _legacy_fixed():
    return dict(chain=dict(baseline="c65ff4e25ea6373aabf8db25d304ee7614b96eb5",
        closure="1491765c64c60a63d6bddf10a049308e404885ca", implementation=legacy.LEGACY_COMMIT,
        tree=legacy.LEGACY_TREE),
        archive=dict(basename="q2-history-readonly-return-20260927T151622+0800.tar.gz", bytes=38014204,
                     sha256="869a859fcbe7a952d11e22db6f6534c9b9a3025cec27471fe3e2a054a6a96018"),
        manifest=dict(bytes=legacy.MANIFEST_PIN[0], sha256=legacy.MANIFEST_PIN[1]),
        inventory=dict(unique_blobs=48, blob_bytes=5686734, reservation_inputs=10, trees=12,
                       old_pins=15, typed_sources=47, forward_entries=610, reconciliation_rows=7),
        producer_blobs=dict(LEGACY_BLOBS))


def _horizon_relation():
    snapshot = next(row for row in horizon.source_members()
                    if (row["batch"], row["role"]) == ("20261001e", "historical-snapshot"))
    return dict(archives=[dict(batch=batch, basename=name, bytes=size, sha256=pin)
                         for batch, name, size, pin in horizon.ARCHIVES],
        source_members=horizon.source_members(),
        snapshot=dict(path=snapshot["path"], bytes=snapshot["bytes"], sha256=snapshot["sha256"],
                      rows=24, rows_bytes=horizon.VECTOR_PINS["snapshot"][0],
                      rows_sha256=horizon.VECTOR_PINS["snapshot"][1], total_bytes=626790400, total_inodes=32113),
        predecessor=dict(baseline="ae50aea2639c32021794ecb70730f4b9e781c8d6",
            event="LH-Q2-SYSTEM-MANAGER-REPAIR-CLOSURE-20261001-01",
            closure="23702d6e55396d7941389817ab875a4610d3e142",
            implementation="6470592cc29efb45b8f38172b8e69a48fcfeab2a",
            candidate="1a900e4a38e9567655f21cbf3c3f17941de1a8d5",
            corrected_package=dict(basename="local-hand-system-manager-1a900e4-20261001e-corrected.zip",
                bytes=3887651, sha256="5805dcd2a45f150f0e5b7062a17b46137d53e889e1ea160601d7c75fb529e886"),
            evidence_package={k: v for k, v in dict(zip(("batch", "basename", "bytes", "sha256"),
                                                       horizon.ARCHIVES[-1], strict=True)).items() if k != "batch"}))


def _producer_relation():
    delta = horizon.delta_rows()
    value = dict(adoption_baseline="68424df2ddbf812b9479ffa7a64dcaa59a2a9f76",
        adoption_closure="179652cb9487163d83c004d358e4d4b49409694c",
        adoption_implementation="4b71824a4660723d064969cbf0c39cd4325dd62a",
        commit="661e96772c64433d1cd0eebf122e165781d8c11c", tree="2e977e9887f9e6e1a97b86082d1664772c0f7e3b",
        path="tests/e3_host/q2_old_producer_admission_retry_accounting.py",
        blob="659df7ee2bab92413fa41d348c17219e4d9de0c7", file_sha256=PRODUCER_SHA256,
        categories=[dict(category=row["category"], commitment=row["commitment"]) for row in delta],
        device_selectors={row["category"]: row["device_selector"] for row in delta})
    _vector(value, (1778, "851583a3a5268cb43fcd50990b2ef297f45fa7fe6e3ad679e9ea5af8ed978ab1"), "PRODUCER_VECTOR")
    return value


def _preflight_member(pointer):
    row = next(row for row in horizon.source_members()
               if (row["batch"], row["role"]) == ("20261001e", "preflight"))
    return dict(row, pointer=pointer)


def _quota_relation():
    project_ids = list(range(10001, 10005)) + list(range(11001, 11008))
    for start in (12001, 12011, 12021, 12031, 12041):
        project_ids.extend(range(start, start + 7))
    return dict(schema="local-hand-q2-core-configured-quota-liability/v1",
        source_member=_preflight_member("/capacity_observed/quota_inventory"), project_ids=project_ids,
        rows_sha256=horizon.VECTOR_PINS["quota"][1], total_bytes=249561088, total_inodes=17792,
        relation="UNMATCHED_CONFIGURED_HARD_LIMITS_ADDED_ONCE", zero_mismatch=True)


def _placement_relation():
    return dict(schema="local-hand-q2-core-obligation-placement/v1",
        source_member=_preflight_member("/capacity_observed/historical_physical_charges"), source_rows=24,
        source_rows_bytes=horizon.VECTOR_PINS["placement_source"][0],
        source_rows_sha256=horizon.VECTOR_PINS["placement_source"][1],
        normalized_rows_bytes=horizon.VECTOR_PINS["placement_normalized"][0],
        normalized_rows_sha256=horizon.VECTOR_PINS["placement_normalized"][1],
        snapshot_profile="PINNED_ROLE_POOLS_FULL_COMMITMENT_PER_DISTINCT_LIVE_POOL",
        delta_profile="FIXED_SINGLE_SELECTOR_POOL_FULL_COMMITMENT", split_allowed=False, zero_mismatch=True)


def _union(relation):
    obligations = relation["obligations"]
    return dict(schema="local-hand-q2-core-source-union/v1", locator=relation["locator"],
        **{key: obligations[key] for key in ("legacy_20260927", "horizon_20261001e", "producer",
                                            "configured_quota_liability", "placement")},
        later_nonissuance=relation["later_nonissuance"])


def _read_locators(carriers):
    _require(type(carriers) is dict and set(carriers) == {row[0] for row in LOCATOR_CARRIERS}, "LOCATOR_CARRIERS")
    for role, size, digest in LOCATOR_CARRIERS:
        _pin(carriers[role], size, digest, "LOCATOR_CARRIER_PIN")
    selected, seen = {}, set()
    by_path = {path: (role, size, digest) for role, path, size, digest in LOCATOR_MEMBERS}
    try:
        with tarfile.open(fileobj=io.BytesIO(carriers["guest_raw"]), mode="r:gz") as archive:
            for item in archive:
                _require(item.name not in seen and len(seen) < 32768, "LOCATOR_ARCHIVE_MEMBERS")
                seen.add(item.name)
                if item.name not in by_path:
                    continue
                role, size, digest = by_path[item.name]
                _require(item.isfile() and not item.issym() and not item.islnk() and item.size == size,
                         "LOCATOR_MEMBER_TYPE")
                stream = archive.extractfile(item)
                _require(stream is not None, "LOCATOR_MEMBER_MISSING")
                with stream:
                    raw = stream.read(size + 1)
                _pin(raw, size, digest, "LOCATOR_MEMBER_PIN")
                selected[role] = horizon._json(raw)
    except (OSError, EOFError, tarfile.TarError) as error:
        raise c.ContractError("CORE_APPROVED_INPUTS_LOCATOR_ARCHIVE") from error
    _require(set(selected) == {row[0] for row in LOCATOR_MEMBERS}, "LOCATOR_MEMBER_SET")
    # Resolve every mapping, including non-retained locators; a relation row is
    # never considered verified merely because it names the correct pointer.
    values = {}
    for role, source, pointer, transform in LOCATOR_MAPPINGS:
        value = selected[source]
        for part in pointer.split("/")[1:]:
            _require(type(value) is dict and part in value, "LOCATOR_POINTER")
            value = value[part]
        if transform == "source_order_identity_array":
            _require(type(value) is list, "LOCATOR_ARRAY")
        else:
            _require(type(value) is str and value and value.isascii(), "LOCATOR_STRING")
            if transform == "dirname":
                c.absolute_path(value)
                value = str(PurePosixPath(value).parent)
                _require(value != "/", "LOCATOR_PARENT")
        values[role] = copy.deepcopy(value)
    return selected, values


def _verified_legacy(sources):
    manifest, blobs = legacy.recover_inputs(sources.legacy_frame, sources.historical_tools)
    verified = _run_legacy_verifier(manifest, blobs, sources.historical_tools)
    _require(len(verified.obligations) == 7 and len(verified.historical_trees) == 12
             and len(verified.manifest["sources"]) == 47 and len(verified.reservation_records) == 10
             and len(verified.forward_baseline["entries"]) == 610
             and len(verified.metadata_baselines) == 5, "LEGACY_INVENTORY")
    return verified


def _run_legacy_verifier(manifest, blobs, historical_tools):
    """Run only the pure verifier from the manifest-pinned historical closure.

    Current checkout helpers are deliberately not substituted for legacy D.
    The established in-memory loader preserves original source paths, admits
    only those exact 42 hash-bound files, and restores its temporary import
    hook on every exit. It writes no files and calls no historical entry point.
    These are explicitly trusted Git-pinned interpreter bytes, not evidence
    archive members selected for execution.
    """
    _pin(manifest, *legacy.MANIFEST_PIN, "LEGACY_MANIFEST_PIN")
    document = horizon._json(manifest)
    source = document["execution"]["source"]
    c.exact(source, {"commit", "tree", "files"})
    _require(source["commit"] == legacy.LEGACY_COMMIT and source["tree"] == legacy.LEGACY_TREE,
             "LEGACY_SOURCE_IDENTITY")
    _require(type(historical_tools) is dict and len(historical_tools) == 42
             and type(source["files"]) is dict and len(source["files"]) == 42, "LEGACY_TOOL_CLOSURE")
    files, names = {}, set()
    for path, pin in source["files"].items():
        c.absolute_path(path); c.digest(pin)
        name = PurePosixPath(path).name
        _require(name in historical_tools and name not in names, "LEGACY_TOOL_SET")
        raw = historical_tools[name]
        _require(type(raw) is bytes and c.sha256(raw) == pin, "LEGACY_TOOL_DIGEST")
        names.add(name); files[path] = raw
    _require(names == set(historical_tools), "LEGACY_TOOL_SET")
    for role, pin in LEGACY_BLOBS.items():
        raw = historical_tools["q2_" + role + ".py"]
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        _require(actual == pin, "LEGACY_PRODUCER_BLOB")
    from . import q2_retry_bundle
    path = next(path for path in files if PurePosixPath(path).name == "q2_reconciliation_sources.py")
    with q2_retry_bundle.virtual_tools(files, source["files"]) as loader:
        verifier = loader.load(path, "_q2_core_approved_legacy_verifier")
        _require(callable(getattr(verifier, "verify", None)), "LEGACY_VERIFIER")
        return verifier.verify(manifest, legacy.MANIFEST_PIN[1], blobs,
                               implementation_commit=legacy.LEGACY_COMMIT)


def _legacy_relation(verified):
    rows = []
    parent = PurePosixPath(verified.previous["candidate"]["source"]).parent
    expected_paths = (str(parent) + ".intent.json", str(parent / "bootstrap-attestation.json"))
    for (identifier, size, digest), path in zip(ADOPTED_RAW, expected_paths, strict=True):
        expected = dict(id=identifier, path=path, bytes=size, sha256=digest,
                        source_class="CURRENT_OWNER_SUPPLIED_RAW", proof_id="owner-adoption")
        matches = [row for row in verified.manifest["sources"] if row["id"] == identifier]
        _equal(matches, [expected], "LEGACY_ADOPTION_SOURCE")
        rows.append(expected)
    return dict(_legacy_fixed(), adoption=dict(current_owner_supplied_raw=rows,
        forward_baseline_entries=copy.deepcopy(verified.forward_baseline["entries"]),
        disclosed_atime_changes=copy.deepcopy(verified.metadata_baselines), run_permission_adopted=False,
        released_bytes=0, released_inodes=0))


def _derive(sources):
    _require(type(sources) is ApprovedInputSources, "SOURCES_TYPE")
    c.validate_amendment(sources.amendment)
    _require(type(sources.later_reviews) is dict
             and set(sources.later_reviews) == {row[2] for row in LATER_REVIEWS}, "LATER_SOURCE_SET")
    for _scope, _batch, path, pin in LATER_REVIEWS:
        raw = sources.later_reviews[path]
        _require(type(raw) is bytes and c.sha256(raw) == pin, "LATER_SOURCE_PIN")
    _require(type(sources.producer_raw) is bytes and c.sha256(sources.producer_raw) == PRODUCER_SHA256,
             "PRODUCER_SOURCE_PIN")
    documents, locators = _read_locators(sources.locator_carriers)
    verified = _verified_legacy(sources)
    _equal(verified.original, documents["original_plan"], "LEGACY_LOCATOR_ORIGINAL")
    vectors = horizon.build_horizon(sources.horizon_archives)
    runtime = prior_attempt.runtime_parent_binding(documents['original_plan'], documents['retry_preparation'],
        horizon.read_horizon(sources.horizon_archives)['20261001e', 'plan'])
    _equal(runtime, sources.journal_frozen['runtime_parent_binding'], 'RUNTIME_SOURCE_BINDING')
    _equal(list(verified.obligations), vectors["snapshot_rows"][:7], "LEGACY_PREFIX")
    relation = dict(schema="local-hand-q2-core-approved-source-relation/v1", locator=_locator_relation(),
        obligations=dict(schema="local-hand-q2-core-approved-obligation-sources/v1",
            legacy_20260927=_legacy_relation(verified), horizon_20261001e=_horizon_relation(),
            producer=_producer_relation(), configured_quota_liability=_quota_relation(),
            placement=_placement_relation(), row_relation=vectors["row_relation"], source_horizon="20261001e",
            snapshot_rows_sha256=horizon.VECTOR_PINS["snapshot"][1], delta_rows_sha256=horizon.VECTOR_PINS["delta"][1],
            effective_rows_sha256=horizon.VECTOR_PINS["effective"][1], source_union_sha256="",
            run_permission_adopted=False, zero_mismatch=True),
        later_nonissuance=_later_relation(), zero_mismatch=True)
    relation["obligations"]["source_union_sha256"] = _hash(_union(relation))
    retained = dict(paths=locators["retained_paths"], domains=locators["retained_domains"])
    prior = prior_attempt.build_all(sources.prior_core_files)
    diagnostic = prior_attempt.build_diagnostic(sources.prior_diagnostic_files)
    historical = dict(schema="local-hand-q2-core-historical-capacity-obligations/v18", source_horizon="20261001e",
        source_union_sha256=relation["obligations"]["source_union_sha256"],
        **{key: vectors[key] for key in ("snapshot_rows", "delta_rows", "effective_rows", "row_relation",
                                       "configured_quota_rows", "totals")},
        placement=relation["obligations"]["placement"], released_or_refunded=False,
        maintenance=prior_attempt.maintenance_commitments(),
        prior_commitments=[prior_attempt.commitment(item, index=index) for index, item in enumerate(prior)])
    return dict(schema=SCHEMA, scope=c.SCOPE, amendment=copy.deepcopy(sources.amendment),
        source_relation=relation,
        policy_basis=policy.build_policy_basis(source_raw=sources.policy_sources, tokens=sources.remote_tokens),
        historical_capacity_obligations=historical, retained_preparation=retained,
        reconciliation=dict(copy.deepcopy(RECONCILIATION),
            schema="local-hand-q2-core-reconciliation/v18", prior_core_attempts=prior,
            prior_diagnostic_capture=diagnostic,
            journal_transition=prior_attempt.build_journal_transition(sources.journal_files,
                implementation=sources.amendment['implementation'],sources=sources.journal_sources,
                frozen=sources.journal_frozen,priors=prior)))


def build(*, sources):
    """Build, then independently compare every component with the same raw closure."""
    raw = c.canonical(_derive(sources), newline=True, limit=LIMIT)
    validate(raw, sources=sources)
    return raw


def _adoption(value):
    c.exact(value, {"current_owner_supplied_raw", "forward_baseline_entries", "disclosed_atime_changes",
                    "run_permission_adopted", "released_bytes", "released_inodes"})
    _require(value["run_permission_adopted"] is False and type(value["released_bytes"]) is int
             and type(value["released_inodes"]) is int and value["released_bytes"] == value["released_inodes"] == 0,
             "LEGACY_PERMISSION")
    rows = value["current_owner_supplied_raw"]
    _require(type(rows) is list and len(rows) == 2, "LEGACY_ADOPTION_COUNT")
    for row, (identifier, size, digest) in zip(rows, ADOPTED_RAW, strict=True):
        c.absolute_path(row.get("path"))
        _equal(row, dict(id=identifier, path=row["path"], bytes=size, sha256=digest,
                         source_class="CURRENT_OWNER_SUPPLIED_RAW", proof_id="owner-adoption"), "LEGACY_ADOPTION")
    _require(rows[0]["path"].endswith(".intent.json")
             and rows[1]["path"] == rows[0]["path"][:-len(".intent.json")] + "/bootstrap-attestation.json",
             "LEGACY_ADOPTION_PATH_RELATION")
    forward = value["forward_baseline_entries"]
    _require(type(forward) is list and len(forward) == 610, "LEGACY_FORWARD_COUNT")
    seen, by_path = set(), {}
    for row in forward:
        _require(type(row) is dict and set(row) in ({"source_metadata", "sha256"},
                     {"source_metadata", "sha256", "link_target"}), "LEGACY_FORWARD_FIELDS")
        meta = row["source_metadata"]
        fields = {"device", "inode", "st_mode", "uid", "gid", "nlink", "size", "blocks",
                  "atime_ns", "mtime_ns", "ctime_ns", "path", "type"}
        c.exact(meta, fields)
        c.absolute_path(meta["path"])
        for key in fields - {"path", "type"}:
            c.integer(meta[key], 1 if key in ("device", "inode", "nlink") else 0)
        identity = meta["device"], meta["inode"]
        _require(identity not in seen and meta["path"] not in by_path, "LEGACY_FORWARD_ALIAS")
        seen.add(identity); by_path[meta["path"]] = row
        _require(meta["type"] in ("regular", "directory", "symlink"), "LEGACY_FORWARD_TYPE")
        _require(stat.S_IFMT(meta["st_mode"]) == {
            "regular": stat.S_IFREG, "directory": stat.S_IFDIR, "symlink": stat.S_IFLNK}[meta["type"]],
            "LEGACY_FORWARD_MODE")
        if meta["type"] == "regular":
            c.digest(row["sha256"])
            _require(meta["nlink"] == 1 and "link_target" not in row, "LEGACY_FORWARD_REGULAR")
        elif meta["type"] == "directory":
            _require(row["sha256"] is None and "link_target" not in row, "LEGACY_FORWARD_DIRECTORY")
        else:
            _require(row["sha256"] is None and type(row.get("link_target")) is str, "LEGACY_FORWARD_SYMLINK")
    _require(list(by_path) == sorted(by_path), "LEGACY_FORWARD_ORDER")
    parent = rows[0]["path"][:-len(".intent.json")]
    _require(parent in by_path and by_path[parent]["source_metadata"]["type"] == "directory"
             and all(path == rows[0]["path"] or path == parent or path.startswith(parent + "/")
                     for path in by_path), "LEGACY_FORWARD_ROOT")
    for row in rows:
        _require(row["path"] in by_path and by_path[row["path"]]["sha256"] == row["sha256"]
                 and by_path[row["path"]]["source_metadata"]["size"] == row["bytes"], "LEGACY_FORWARD_ADOPTED")
    changed = value["disclosed_atime_changes"]
    _require(type(changed) is dict and len(changed) == 5, "LEGACY_ATIME_COUNT")
    for path, row in changed.items():
        c.absolute_path(path)
        c.exact(row, {"source_class", "sha256", "source_metadata", "historical_atime_preservation_proven"})
        _require(row["source_class"] == "POST_READ_METADATA_BASELINE"
                 and row["historical_atime_preservation_proven"] is False, "LEGACY_ATIME_CLASS")
        c.digest(row["sha256"])
        c.exact(row["source_metadata"], fields - {"path", "type"})
        for field, number in row["source_metadata"].items():
            c.integer(number, 1 if field in ("device", "inode", "nlink") else 0)
        if path in by_path:
            _equal(row["source_metadata"], {key: item for key, item in by_path[path]["source_metadata"].items()
                                          if key not in ("path", "type")}, "LEGACY_ATIME_METADATA")
            _require(row["sha256"] == by_path[path]["sha256"], "LEGACY_ATIME_DIGEST")


def _validate_relations(value):
    relation = value["source_relation"]
    c.exact(relation, {"schema", "locator", "obligations", "later_nonissuance", "zero_mismatch"})
    _require(relation["schema"] == "local-hand-q2-core-approved-source-relation/v1"
             and relation["zero_mismatch"] is True, "SOURCE_RELATION")
    _equal(relation["locator"], _locator_relation(), "LOCATOR_RELATION")
    _equal(relation["later_nonissuance"], _later_relation(), "LATER_RELATION")
    obligations = relation["obligations"]
    fields = {"schema", "legacy_20260927", "horizon_20261001e", "producer", "configured_quota_liability",
              "placement", "row_relation", "source_horizon", "snapshot_rows_sha256", "delta_rows_sha256",
              "effective_rows_sha256", "source_union_sha256", "run_permission_adopted", "zero_mismatch"}
    c.exact(obligations, fields)
    _require(obligations["schema"] == "local-hand-q2-core-approved-obligation-sources/v1"
             and obligations["source_horizon"] == "20261001e" and obligations["zero_mismatch"] is True
             and obligations["run_permission_adopted"] is False, "OBLIGATION_RELATION")
    old = obligations["legacy_20260927"]
    c.exact(old, {*_legacy_fixed(), "adoption"})
    _equal({key: item for key, item in old.items() if key != "adoption"}, _legacy_fixed(), "LEGACY_FIXED")
    _adoption(old["adoption"])
    for key, expected in (("horizon_20261001e", _horizon_relation()), ("producer", _producer_relation()),
                          ("configured_quota_liability", _quota_relation()), ("placement", _placement_relation())):
        _equal(obligations[key], expected, "RELATION_" + key.upper())
    _vector(obligations["row_relation"], horizon.VECTOR_PINS["row_relation"], "ROW_RELATION")
    for field, name in (("snapshot_rows_sha256", "snapshot"), ("delta_rows_sha256", "delta"),
                        ("effective_rows_sha256", "effective")):
        _require(obligations[field] == horizon.VECTOR_PINS[name][1], "ROW_DIGEST")
    _require(obligations["source_union_sha256"] == _hash(_union(relation)), "SOURCE_UNION")
    return obligations


def _validate_capacity(value, obligations):
    c.exact(value, {"schema", "source_horizon", "source_union_sha256", "snapshot_rows", "delta_rows",
                    "effective_rows", "row_relation", "placement", "configured_quota_rows", "totals",
                    "released_or_refunded", "prior_commitments", "maintenance"})
    _require(value["schema"] == "local-hand-q2-core-historical-capacity-obligations/v18"
             and value["source_horizon"] == "20261001e" and value["released_or_refunded"] is False,
             "CAPACITY_SCHEMA")
    _equal(value["maintenance"],prior_attempt.maintenance_commitments(),"MAINTENANCE_COMMITMENTS")
    for key in ("source_union_sha256", "row_relation", "placement"):
        _equal(value[key], obligations[key], "CAPACITY_RELATION")
    for key, name in (("snapshot_rows", "snapshot"), ("delta_rows", "delta"),
                      ("effective_rows", "effective"), ("configured_quota_rows", "quota")):
        _vector(value[key], horizon.VECTOR_PINS[name], "CAPACITY_" + name.upper())
    _equal(value["effective_rows"], value["snapshot_rows"] + value["delta_rows"], "CAPACITY_CONSTRUCTION")
    _require(_hash(value["snapshot_rows"][:7]) == horizon.PREFIX_SHA256
             and _hash(value["snapshot_rows"][7:]) == horizon.TAIL_SHA256, "CAPACITY_PREFIX")
    _equal(value["totals"], horizon.TOTALS, "CAPACITY_TOTALS")
    for key, count in (("snapshot_rows", 24), ("delta_rows", 12), ("effective_rows", 36)):
        rows = value[key]
        _require(type(rows) is list and len(rows) == count, "CAPACITY_COUNT")
        prefix = key.removesuffix("_rows")
        for field in ("bytes", "inodes"):
            _require(sum(c.integer(row["commitment"][field]) for row in rows)
                     == value["totals"][prefix + "_" + field], "CAPACITY_SUM")
    _require([row["project_id"] for row in value["configured_quota_rows"]]
             == obligations["configured_quota_liability"]["project_ids"], "CAPACITY_PROJECTS")


def _validate_retained(value):
    c.exact(value, {"paths", "domains"})
    for key in ("paths", "domains"):
        _vector(value[key], RETAINED_PINS[key], "RETAINED_" + key.upper())
    _vector(value, RETAINED_PINS["object"], "RETAINED_OBJECT")
    _require(len(value["paths"]) == 16 and len(value["domains"]) == 4, "RETAINED_COUNT")
    for row in value["paths"]:
        c.exact(row, {"path", "device", "inode"})
        c.absolute_path(row["path"]); c.integer(row["device"], 1); c.integer(row["inode"], 1)
    for row in value["domains"]:
        c.exact(row, {"project_id", "hard_bytes", "inode_hard_limit"})
        for number in row.values():
            c.integer(number, 1)


def _validate_policy(value):
    c.exact(value, {"schema", "fixture_cloud_config", "identity_public", "known_hosts",
                    "remote_expectation", "policies", "policy_predicates_sha256"})
    _require(value["schema"] == policy.SCHEMA, "POLICY_SCHEMA")
    for name, digest in policy.SOURCE_PINS.items():
        _equal(value[name], dict(binding_pointer="/" + name, sha256=digest), "POLICY_SOURCE")
    expected = copy.deepcopy(value["remote_expectation"])
    _require(type(expected) is dict, "POLICY_EXPECTATION")
    for key in ("remote_tokens_sha256", "remote_command_sha256"):
        c.digest(expected.get(key))
        expected[key] = ""
    # These template pins cover every fixed key and scalar in A §3.2. Only the
    # two D-dependent command digests and source-derived key are normalized.
    # The parser does not call the policy builder, so rehashing a weakened
    # predicate cannot turn it into a valid predicate.
    _vector(expected, (410, "307997766eca2a5bef0411b6a41e72c1e904fa74831a03659e26a61b5c1d80cd"),
            "POLICY_EXPECTATION_TEMPLATE")
    policies = value["policies"]
    c.exact(policies, {"sudo", "sshd", "authorized_keys", "rc"})
    _require(value["policy_predicates_sha256"] == _hash(policies), "POLICY_DIGEST")
    normalized = copy.deepcopy(policies)
    for name, item in policies.items():
        c.exact(item, {"schema", "mode", "sources", "paths", "argv", "environment", "execution",
                       "predicate", "limits", "predicate_sha256"})
        _require(item["predicate_sha256"] == _hash(item["predicate"]), "POLICY_PREDICATE_DIGEST")
        normalized[name]["predicate_sha256"] = ""
    try:
        key = policies["authorized_keys"]["predicate"]["parameters"]["approved_key"]
        c.exact(key, {"type", "key_base64", "source_sha256"})
        _require(type(key["key_base64"]) is str and key["key_base64"].isascii(), "POLICY_KEY")
        _equal(key, policy._key(("ssh-ed25519 " + key["key_base64"] + "\n").encode("ascii")), "POLICY_KEY")
        target = normalized["authorized_keys"]["predicate"]["parameters"]["approved_key"]
        target["key_base64"] = target["source_sha256"] = ""
    except (KeyError, TypeError) as error:
        raise c.ContractError("CORE_APPROVED_INPUTS_POLICY_KEY") from error
    _vector(normalized, (6574, "b70e64bb418db787b2e7756f70d5e605329a00008a970aaf9939a32104e8506a"),
            "POLICY_PREDICATE_TEMPLATE")


def component_digests(value):
    """The six artifact/component bindings; JIT bindings are supplied separately."""
    return dict(approved_inputs_sha256=c.sha256(c.canonical(value, newline=True)),
        **{key + "_sha256": _hash(value[key]) for key in (
            "policy_basis", "historical_capacity_obligations", "retained_preparation", "reconciliation")},
        approved_source_relation_sha256=_hash(value["source_relation"]))


def _verify_cloud_grant(raw, parameters):
    """Independent block/field check; never calls the policy mapping builder."""
    _require(type(raw) is bytes and c.sha256(raw) == policy.SOURCE_PINS['fixture_cloud_config'],
             'SOURCE_POLICY_PIN')
    lines = policy.cloud_source_lines(raw)
    indices = {key: [i for i, line in enumerate(lines)
                    if re.match(r' *(?:- )?' + key + r':', line)]
               for key in ('users', 'name', 'sudo')}
    _require(all(len(rows) == 1 for rows in indices.values()), 'SOURCE_POLICY_GRANT')
    start = indices['users'][0]
    end = next((i for i in range(start + 1, len(lines)) if not lines[i].startswith(' ')), len(lines))
    _require(lines[start] == 'users:' and start + 1 == indices['name'][0]
             and lines[start + 1] == '  - name: q1admin'
             and start + 1 < indices['sudo'][0] < end, 'SOURCE_POLICY_GRANT')
    fields, current = {}, None
    for line in lines[start + 2:end]:
        if line.startswith('      - ssh-ed25519 '):
            _require(current == 'ssh_authorized_keys'
                     and re.fullmatch(r'      - ssh-ed25519 [A-Za-z0-9+/=]+(?: [A-Za-z0-9_.@+-]+)?', line),
                     'SOURCE_POLICY_GRANT')
            continue
        match = re.fullmatch(r'    ([a-z_]+):(?: (.+))?', line)
        _require(match is not None and match[1] not in fields and match[1] != 'name', 'SOURCE_POLICY_GRANT')
        current = match[1]
        fields[current] = match[2]
    _require(fields.get('sudo') == '["ALL=(ALL) NOPASSWD:ALL"]', 'SOURCE_POLICY_GRANT')
    for key, value in fields.items():
        if key == 'sudo':
            continue
        _require((key == 'ssh_authorized_keys' and value is None) or
                 (key != 'ssh_authorized_keys' and value is not None
                  and re.fullmatch(r'[A-Za-z0-9_./,@+= -]+|\[[A-Za-z0-9_, -]+\]', value)),
                 'SOURCE_POLICY_GRANT')
    _require(parameters['account'] == 'q1admin' and parameters['cloud_config_literal'] == policy.GRANT
             and type(parameters['cloud_config_literal_count']) is int
             and parameters['cloud_config_literal_count'] == 1, 'SOURCE_POLICY_GRANT')


def _verify_sources(value, sources):
    """Second path: compare each parsed component to raw inputs, never _derive.

    The bounded archive decoders and historically pinned legacy interpreter are
    shared primitives. The aggregate construction, policy builder and horizon
    aggregate builder are not used by this verification path.
    """
    _require(type(sources) is ApprovedInputSources, "SOURCES_TYPE")
    _equal(value["amendment"], sources.amendment, "SOURCE_AMENDMENT")
    _require(type(sources.later_reviews) is dict
             and set(sources.later_reviews) == {row[2] for row in LATER_REVIEWS}, "LATER_SOURCE_SET")
    for _scope, _batch, path, pin in LATER_REVIEWS:
        raw = sources.later_reviews[path]
        _require(type(raw) is bytes and c.sha256(raw) == pin, "LATER_SOURCE_PIN")
    _require(type(sources.producer_raw) is bytes and c.sha256(sources.producer_raw) == PRODUCER_SHA256,
             "PRODUCER_SOURCE_PIN")
    documents, locators = _read_locators(sources.locator_carriers)
    _equal(value["retained_preparation"], dict(paths=locators["retained_paths"],
             domains=locators["retained_domains"]), "SOURCE_RETAINED")
    verified = _verified_legacy(sources)
    _equal(verified.original, documents["original_plan"], "SOURCE_LEGACY_ORIGINAL")
    capacity = value["historical_capacity_obligations"]
    _equal(list(verified.obligations), capacity["snapshot_rows"][:7], "SOURCE_LEGACY_PREFIX")
    adopted = value["source_relation"]["obligations"]["legacy_20260927"]["adoption"]
    for identifier, _size, _digest in ADOPTED_RAW:
        actual = [row for row in adopted["current_owner_supplied_raw"] if row["id"] == identifier]
        original = [row for row in verified.manifest["sources"] if row["id"] == identifier]
        _equal(actual, original, "SOURCE_ADOPTED_RAW")
    _equal(adopted["forward_baseline_entries"], verified.forward_baseline["entries"], "SOURCE_FORWARD_BASELINE")
    _equal(adopted["disclosed_atime_changes"], verified.metadata_baselines, "SOURCE_ATIME_DISCLOSURE")
    retained = horizon.read_horizon(sources.horizon_archives)
    runtime = prior_attempt.runtime_parent_binding(documents['original_plan'],
        documents['retry_preparation'], retained['20261001e', 'plan'])
    _equal(value['reconciliation']['journal_transition']['runtime_parent_binding'],
        runtime, 'SOURCE_RUNTIME_BINDING')
    snapshot = retained["20261001e", "historical-snapshot"]
    _require(snapshot.get("historical_plan_executed") is False
             and snapshot.get("released_or_refunded") is False, "SOURCE_SNAPSHOT_PERMISSION")
    _equal(capacity["snapshot_rows"], snapshot["obligations"], "SOURCE_SNAPSHOT")
    preflight = retained["20261001e", "preflight"]["capacity_observed"]
    quota = []
    for item in preflight["quota_inventory"]:
        for field in ("project", "hard", "ihard"):
            c.integer(item[field])
        if item["hard"] > 0:
            quota.append(dict(project_id=item["project"], hard_bytes=c.integer(item["hard"] * 1024),
                              inode_hard_limit=item["ihard"]))
    _equal(capacity["configured_quota_rows"], quota, "SOURCE_QUOTA")
    physical = preflight["historical_physical_charges"]
    _vector(physical, horizon.VECTOR_PINS["placement_source"], "SOURCE_PLACEMENT")
    mounts = retained["20261001e", "plan"]["mounts"]
    c.exact(mounts, {"system", "quota", "journal", "evidence"})
    devices = {c.integer(item["device"], 1): role for role, item in mounts.items()}
    _require(len(devices) == 4 and len(physical) == 24, "SOURCE_PLACEMENT_DEVICES")
    normalized = []
    for row, obligation in zip(physical, capacity["snapshot_rows"], strict=True):
        c.exact(row, {"id", "category", "devices", "full_commitment", "no_refund"})
        _require(row["id"] == obligation["id"] and row["category"] == obligation["category"]
                 and row["full_commitment"] == obligation["commitment"] and row["no_refund"] is True,
                 "SOURCE_PLACEMENT_ROW")
        _require(type(row["devices"]) is list and row["devices"]
                 and all(type(device) is int and device in devices for device in row["devices"])
                 and len(set(row["devices"])) == len(row["devices"]), "SOURCE_PLACEMENT_ROW_DEVICES")
        normalized.append(dict(id=row["id"], category=row["category"],
            pool_roles=[devices[device] for device in row["devices"]],
            full_commitment=row["full_commitment"], no_refund=True))
    _vector(normalized, horizon.VECTOR_PINS["placement_normalized"], "SOURCE_PLACEMENT_NORMALIZED")
    _require(type(sources.policy_sources) is dict and set(sources.policy_sources) == set(policy.SOURCE_PINS),
             "SOURCE_POLICY_SET")
    for name, pin in policy.SOURCE_PINS.items():
        raw = sources.policy_sources[name]
        _require(type(raw) is bytes and c.sha256(raw) == pin, "SOURCE_POLICY_PIN")
    _verify_cloud_grant(sources.policy_sources['fixture_cloud_config'],
        value['policy_basis']['policies']['sudo']['predicate']['parameters'])
    expected = value["policy_basis"]["remote_expectation"]
    _require(type(sources.remote_tokens) is list and sources.remote_tokens
             and all(type(token) is str and token and "\0" not in token for token in sources.remote_tokens),
             "SOURCE_TOKENS")
    _require(expected["remote_tokens_sha256"] == _hash(sources.remote_tokens)
             and expected["remote_command_sha256"] == c.sha256(shlex.join(sources.remote_tokens).encode("utf-8")),
             "SOURCE_COMMAND")
    _equal(value["policy_basis"]["policies"]["authorized_keys"]["predicate"]["parameters"]["approved_key"],
           policy._key(sources.policy_sources["identity_public"]), "SOURCE_POLICY_KEY")


def validate(raw, *, sources=None):
    """Strict artifact parser, optionally checked against the retained raw closure.

    Fixed hash pins authenticate the row vectors; recomputed cross-relations
    reject self-consistent substitutions and duplicate accounting. Source-less
    parsing cannot prove that a private input closure was actually collected.
    """
    try:
        value = c.document(raw, limit=LIMIT, newline=True)
        c.exact(value, FIELDS)
        _require(value["schema"] == SCHEMA and value["scope"] == c.SCOPE, "SCHEMA")
        c.validate_amendment(value["amendment"])
        obligations = _validate_relations(value)
        _validate_capacity(value["historical_capacity_obligations"], obligations)
        _validate_retained(value["retained_preparation"])
        reconciliation = value["reconciliation"]
        c.exact(reconciliation, {*RECONCILIATION, "schema", "prior_core_attempts", "prior_diagnostic_capture", "journal_transition"})
        _require(reconciliation["schema"] == "local-hand-q2-core-reconciliation/v18", "RECONCILIATION_SCHEMA")
        _equal({key: reconciliation[key] for key in RECONCILIATION}, RECONCILIATION, "RECONCILIATION")
        prior = reconciliation["prior_core_attempts"]
        prior_attempt.validate_all(prior)
        prior_attempt.validate_journal_transition(reconciliation["journal_transition"],priors=prior,
            implementation=value["amendment"]["implementation"])
        prior_attempt.validate_diagnostic(reconciliation['prior_diagnostic_capture'])
        _equal(value["historical_capacity_obligations"]["prior_commitments"],
               [prior_attempt.commitment(item, index=index) for index, item in enumerate(prior)],
               "PRIOR_COMMITMENT")
        _validate_policy(value["policy_basis"])
        if sources is not None:
            _equal(prior, prior_attempt.build_all(sources.prior_core_files), "PRIOR_SOURCE")
            _equal(reconciliation['prior_diagnostic_capture'],
                   prior_attempt.build_diagnostic(sources.prior_diagnostic_files), 'DIAGNOSTIC_SOURCE')
            _equal(reconciliation['journal_transition'],
                prior_attempt.build_journal_transition(sources.journal_files,
                    implementation=sources.amendment['implementation'],sources=sources.journal_sources,
                    frozen=sources.journal_frozen,priors=prior), 'JOURNAL_SOURCE')
            _verify_sources(value, sources)
        return value
    except c.ContractError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError, OSError, ValueError) as error:
        raise c.ContractError("CORE_APPROVED_INPUTS_INVALID_SOURCE_OR_SHAPE") from error
