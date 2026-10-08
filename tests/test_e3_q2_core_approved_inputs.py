"""Synthetic boundary tests; none is retained-source or field acceptance."""
import base64
import builtins
import copy
from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import stat
import struct
from types import SimpleNamespace

import pytest

from e3_host import q2_core_approved_inputs as a


def _pin(value):
    raw = a.c.canonical(value)
    return len(raw), hashlib.sha256(raw).hexdigest()


def _rehash(value):
    relation = value["source_relation"]
    pin = a._hash(a._union(relation))
    relation["obligations"]["source_union_sha256"] = pin
    value["historical_capacity_obligations"]["source_union_sha256"] = pin


@pytest.fixture
def artifact(monkeypatch):
    # Private fixed vectors cannot be fabricated. Replace only their pins in
    # this isolated fixture and exercise the full aggregate relation checker.
    snapshot = [dict(id="s" + str(index), category="state", commitment=dict(bytes=1, inodes=1),
                     covered_paths=["/synthetic/s" + str(index)], evidence=["/synthetic/evidence"],
                     accounting_categories=["state"]) for index in range(24)]
    snapshot[-1]["commitment"] = dict(bytes=626790400 - 23, inodes=32113 - 23)
    delta = a.horizon.delta_rows()
    quota = [dict(project_id=pid, hard_bytes=size, inode_hard_limit=count)
             for pid, size, count in ((10001, 67108864, 4096), (10002, 67108864, 4096),
                                      (10003, 4194304, 128), (10004, 67108864, 4096))]
    for first in (11001, 12001, 12011, 12021, 12031, 12041):
        quota.extend(dict(project_id=pid, hard_bytes=1048576, inode_hard_limit=128)
                     for pid in range(first, first + 7))
    prefix, tail = a._hash(snapshot[:7]), a._hash(snapshot[7:])
    monkeypatch.setattr(a.horizon, "PREFIX_SHA256", prefix)
    monkeypatch.setattr(a.horizon, "TAIL_SHA256", tail)
    row_relation = dict(reconciliation_prefix_count=7, reconciliation_prefix_sha256=prefix,
        snapshot_count=24, snapshot_sha256=a._hash(snapshot), snapshot_tail_count=17,
        snapshot_tail_sha256=tail, delta_count=12, effective_count=36,
        effective_construction="SNAPSHOT_24_PLUS_DELTA_12", prefix_equal=True)
    pins = dict(a.horizon.VECTOR_PINS)
    pins.update(snapshot=_pin(snapshot), effective=_pin(snapshot + delta), row_relation=_pin(row_relation))
    monkeypatch.setattr(a.horizon, "VECTOR_PINS", pins)

    parent = "/synthetic/previous"
    adopted = [dict(id=identifier, path=parent + ".intent.json" if index == 0 else parent + "/bootstrap-attestation.json",
                    bytes=size, sha256=digest, source_class="CURRENT_OWNER_SUPPLIED_RAW", proof_id="owner-adoption")
               for index, (identifier, size, digest) in enumerate(a.ADOPTED_RAW)]
    paths = [parent] + [row["path"] for row in adopted] + [parent + "/file-" + str(i).zfill(3) for i in range(607)]
    forward = []
    for index, path in enumerate(sorted(paths)):
        is_root = path == parent
        source = next((row for row in adopted if row["path"] == path), None)
        metadata = dict(device=1, inode=index + 1, st_mode=(stat.S_IFDIR | 0o700) if is_root else (stat.S_IFREG | 0o600),
            uid=0, gid=0, nlink=1, size=source["bytes"] if source else 0, blocks=8,
            atime_ns=1, mtime_ns=2, ctime_ns=3, path=path, type="directory" if is_root else "regular")
        forward.append(dict(source_metadata=metadata, sha256=None if is_root else source["sha256"] if source else "a" * 64))
    metadata_baselines = {}
    for row in [row for row in forward if row["sha256"] is not None][:5]:
        meta = row["source_metadata"]
        metadata_baselines[meta["path"]] = dict(source_class="POST_READ_METADATA_BASELINE", sha256=row["sha256"],
            source_metadata={key: val for key, val in meta.items() if key not in ("path", "type")},
            historical_atime_preservation_proven=False)
    old = dict(a._legacy_fixed(), adoption=dict(current_owner_supplied_raw=adopted,
        forward_baseline_entries=forward, disclosed_atime_changes=metadata_baselines,
        run_permission_adopted=False, released_bytes=0, released_inodes=0))
    retained = dict(paths=[dict(path="/synthetic/retained/" + str(i), device=1, inode=1000+i) for i in range(16)],
                    domains=copy.deepcopy(quota[:4]))
    monkeypatch.setattr(a, "RETAINED_PINS", {**{k: _pin(v) for k, v in retained.items()}, "object": _pin(retained)})

    key = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + b"x" * 32
    policy_raw = dict(fixture_cloud_config=b'#cloud-config\nusers:\n  - name: q1admin\n    sudo: ["ALL=(ALL) NOPASSWD:ALL"]\n',
                      identity_public=b"ssh-ed25519 " + base64.b64encode(key) + b" synthetic\n", known_hosts=b"synthetic\n")
    monkeypatch.setattr(a.policy, "SOURCE_PINS", {k: hashlib.sha256(v).hexdigest() for k, v in policy_raw.items()})
    tokens = ["/synthetic/frozen", "token with space"]
    relation = dict(schema="local-hand-q2-core-approved-source-relation/v1", locator=a._locator_relation(),
        obligations=dict(schema="local-hand-q2-core-approved-obligation-sources/v1", legacy_20260927=old,
            horizon_20261001e=a._horizon_relation(), producer=a._producer_relation(),
            configured_quota_liability=a._quota_relation(), placement=a._placement_relation(),
            row_relation=row_relation, source_horizon="20261001e", snapshot_rows_sha256=a._hash(snapshot),
            delta_rows_sha256=a._hash(delta), effective_rows_sha256=a._hash(snapshot + delta),
            source_union_sha256="", run_permission_adopted=False, zero_mismatch=True),
        later_nonissuance=a._later_relation(), zero_mismatch=True)
    value = dict(schema=a.SCHEMA, scope=a.c.SCOPE, amendment=a.c.make_amendment(dict(commit="d" * 40, tree="e" * 40)),
        source_relation=relation, policy_basis=a.policy.build_policy_basis(source_raw=policy_raw, tokens=tokens),
        historical_capacity_obligations=dict(schema="local-hand-q2-core-historical-capacity-obligations/v1",
            source_horizon="20261001e", source_union_sha256="", snapshot_rows=snapshot, delta_rows=delta,
            effective_rows=snapshot + delta, row_relation=row_relation, placement=a._placement_relation(),
            configured_quota_rows=quota, totals=copy.deepcopy(a.horizon.TOTALS), released_or_refunded=False),
        retained_preparation=retained, reconciliation=copy.deepcopy(a.RECONCILIATION))
    _rehash(value)
    from core_prior_fixture import embed
    embed(value, monkeypatch)
    return value, policy_raw, tokens


def test_full_artifact_and_component_preimages_are_canonical(artifact, monkeypatch):
    value, _raw, _tokens = artifact
    raw = a.c.canonical(value, newline=True)
    # Parser must not rely on the aggregate builder or the policy builder.
    monkeypatch.setattr(a, "_derive", lambda _sources: pytest.fail("parser called aggregate builder"))
    monkeypatch.setattr(a.policy, "build_policy_basis", lambda **_kwargs: pytest.fail("parser called policy builder"))
    assert a.validate(raw) == value
    digests = a.component_digests(value)
    assert digests["approved_inputs_sha256"] == hashlib.sha256(raw).hexdigest()
    assert digests["approved_source_relation_sha256"] == a._hash(value["source_relation"])
    assert digests["approved_inputs_sha256"] != a._hash(value)
    assert set(digests) == {"approved_inputs_sha256", "approved_source_relation_sha256", "policy_basis_sha256",
                            "historical_capacity_obligations_sha256", "retained_preparation_sha256", "reconciliation_sha256"}


@pytest.mark.parametrize("change", ["mapping", "raw_pin", "horizon", "producer", "snapshot", "duplicate_prefix",
                                    "quota", "placement", "source_union", "retained", "refund", "permission",
                                    "later_issued", "adoption_path", "atime", "extra"])
def test_rejects_wrong_sources_relations_and_double_credit_even_with_rehashed_union(artifact, change):
    value, _raw, _tokens = artifact
    value = copy.deepcopy(value)
    relation = value["source_relation"]; obligations = relation["obligations"]
    capacity = value["historical_capacity_obligations"]
    if change == "mapping": relation["locator"]["mappings"].reverse()
    elif change == "raw_pin": relation["locator"]["carriers"][0]["sha256"] = "f" * 64
    elif change == "horizon": obligations["source_horizon"] = "20261001d"
    elif change == "producer": obligations["producer"]["device_selectors"]["management"] = "quota_parent"
    elif change == "snapshot": capacity["snapshot_rows"][0]["commitment"]["bytes"] += 1
    elif change == "duplicate_prefix": capacity["effective_rows"] += capacity["snapshot_rows"][:7]
    elif change == "quota": capacity["configured_quota_rows"] = capacity["configured_quota_rows"][:-1]
    elif change == "placement": obligations["placement"]["split_allowed"] = True
    elif change == "source_union": obligations["source_union_sha256"] = "f" * 64
    elif change == "retained": value["retained_preparation"]["paths"][0]["inode"] += 1
    elif change == "refund": value["reconciliation"]["released_bytes"] = 1
    elif change == "permission": obligations["legacy_20260927"]["adoption"]["run_permission_adopted"] = True
    elif change == "later_issued": relation["later_nonissuance"][0]["state"] = "ISSUED"
    elif change == "adoption_path": obligations["legacy_20260927"]["adoption"]["current_owner_supplied_raw"][1]["path"] += "-other"
    elif change == "atime": obligations["legacy_20260927"]["adoption"]["disclosed_atime_changes"] = {}
    elif change == "extra": value["live_pass"] = True
    if change != "source_union": _rehash(value)
    with pytest.raises(a.c.ContractError):
        a.validate(a.c.canonical(value, newline=True))


@pytest.mark.parametrize("change", ["runas", "argv", "timeout", "environment", "rc", "alias", "extra"])
def test_rehashed_policy_weakening_does_not_pass_template(artifact, change):
    value, _raw, _tokens = artifact
    value = copy.deepcopy(value)
    basis = value["policy_basis"]; policies = basis["policies"]
    if change == "runas": policies["sudo"]["predicate"]["parameters"]["required_grant"]["runas_groups"] = ["ALL"]
    elif change == "argv": policies["sudo"]["argv"].append("-S")
    elif change == "timeout": policies["sshd"]["limits"]["command_seconds"] = 6
    elif change == "environment": policies["rc"]["environment"] = {"BASH_ENV": "/tmp/extra"}
    elif change == "rc": policies["rc"]["predicate"]["parameters"]["required_absent"] = []
    elif change == "alias": basis["remote_expectation"]["aliases"]["sudo"] = "/bin/sudo"
    elif change == "extra": policies["sudo"]["paths"]["accept_unknown"] = True
    for item in policies.values(): item["predicate_sha256"] = a._hash(item["predicate"])
    basis["policy_predicates_sha256"] = a._hash(policies)
    with pytest.raises(a.c.ContractError, match="TEMPLATE"):
        a.validate(a.c.canonical(value, newline=True))


@pytest.mark.parametrize("raw", [b"{}", b"{}\n\n", b'{"a":1,"a":2}\n', b'{"a":1.2}\n',
                                   b'{"a":NaN}\n', b'\xef\xbb\xbf{}\n', b'{"a":9223372036854775808}\n'])
def test_noncanonical_and_ambiguous_json_is_rejected(raw):
    with pytest.raises(a.c.ContractError):
        a.validate(raw)


def test_projection_artifact_validation_does_not_import_linux_runtime(monkeypatch):
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name in {'fcntl', 'pwd', 'resource'} or name.endswith('q2_journal_growth_guest'):
            pytest.fail('portable artifact validation imported Linux runtime: ' + name)
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    value, _policy_raw, _tokens = artifact.__wrapped__(monkeypatch)
    assert a.validate(a.c.canonical(value, newline=True)) == value


def test_production_pins_reject_arbitrary_input_before_any_legacy_interpreter(monkeypatch):
    monkeypatch.setattr(a, "_verified_legacy", lambda _sources: pytest.fail("called legacy before sources verified"))
    with pytest.raises(a.c.ContractError): a.build(sources={})
    with pytest.raises(a.c.ContractError): a._read_locators({})
    carriers = {role: b"unverified" for role, _size, _digest in a.LOCATOR_CARRIERS}
    with pytest.raises(a.c.ContractError, match="LOCATOR_CARRIER_PIN"):
        a._read_locators(carriers)


def source_fixture(artifact, monkeypatch):
    """Replace separately-tested raw decoders, never the aggregate verifier."""
    value, policy_raw, tokens = artifact
    from core_prior_fixture import diagnostic_files
    diagnostic = diagnostic_files(monkeypatch)
    value['reconciliation']['prior_diagnostic_capture'] = a.prior_attempt.build_diagnostic(diagnostic)
    capacity = value["historical_capacity_obligations"]
    old = value["source_relation"]["obligations"]["legacy_20260927"]["adoption"]
    original = dict(retained=value["retained_preparation"]["paths"],
                    retained_domains=value["retained_preparation"]["domains"])
    locators = dict(retained_paths=original["retained"], retained_domains=original["retained_domains"])
    monkeypatch.setattr(a, "_read_locators", lambda _raw: ({"original_plan": original}, locators))
    verified = SimpleNamespace(original=original, obligations=capacity["snapshot_rows"][:7],
        manifest=dict(sources=old["current_owner_supplied_raw"]),
        previous=dict(candidate=dict(source="/synthetic/previous/source")),
        forward_baseline=dict(entries=old["forward_baseline_entries"]), metadata_baselines=old["disclosed_atime_changes"])
    monkeypatch.setattr(a, "_verified_legacy", lambda _sources: verified)
    physical = [dict(id=row["id"], category=row["category"], devices=[1],
                     full_commitment=row["commitment"], no_refund=True) for row in capacity["snapshot_rows"]]
    normalized = [dict(id=row["id"], category=row["category"], pool_roles=["system"],
                       full_commitment=row["commitment"], no_refund=True) for row in capacity["snapshot_rows"]]
    pins = dict(a.horizon.VECTOR_PINS, placement_source=_pin(physical), placement_normalized=_pin(normalized))
    monkeypatch.setattr(a.horizon, "VECTOR_PINS", pins)
    placement = a._placement_relation()
    value["source_relation"]["obligations"]["placement"] = placement
    capacity["placement"] = placement
    quota_input = [dict(project=row["project_id"], hard=row["hard_bytes"] // 1024, ihard=row["inode_hard_limit"])
                   for row in capacity["configured_quota_rows"]]
    retained = {("20261001e", "historical-snapshot"): dict(obligations=capacity["snapshot_rows"],
                                                         historical_plan_executed=False, released_or_refunded=False),
        ("20261001e", "preflight"): dict(capacity_observed=dict(quota_inventory=quota_input,
                                                              historical_physical_charges=physical)),
        ("20261001e", "plan"): dict(mounts={role: dict(device=i + 1)
                                          for i, role in enumerate(("system", "quota", "journal", "evidence"))})}
    monkeypatch.setattr(a.horizon, "read_horizon", lambda _raw: retained)
    later = {path: ("synthetic " + batch).encode() for _scope, batch, path, _pin in a.LATER_REVIEWS}
    monkeypatch.setattr(a, "LATER_REVIEWS", tuple((scope, batch, path, hashlib.sha256(later[path]).hexdigest())
                                                for scope, batch, path, _pin in a.LATER_REVIEWS))
    value["source_relation"]["later_nonissuance"] = a._later_relation()
    _rehash(value)
    producer = Path(a.__file__).with_name("q2_old_producer_admission_retry_accounting.py").read_bytes()
    sources = a.ApprovedInputSources(value["amendment"], {}, {}, b"synthetic boundary", {}, policy_raw,
                                    tokens, later, producer,
        {row['basename']: base64.b64decode(row['raw_base64'])
         for prior in value['reconciliation']['prior_core_attempts'] for row in prior['files']}, diagnostic, {}, {}, {})
    monkeypatch.setattr(a.prior_attempt,'build_journal_transition',lambda *args,**kw:value['reconciliation']['journal_transition'])
    return value, sources


def test_source_verifier_is_independent_of_builders_and_binds_key_tokens_and_raws(artifact, monkeypatch):
    value, sources = source_fixture(artifact, monkeypatch)
    monkeypatch.setattr(a, "_derive", lambda _sources: pytest.fail("source parser called builder"))
    monkeypatch.setattr(a.policy, "build_policy_basis", lambda **_kw: pytest.fail("source parser called policy builder"))
    monkeypatch.setattr(a.horizon, "build_horizon", lambda _raw: pytest.fail("source parser called horizon builder"))
    raw = a.c.canonical(value, newline=True)
    assert a.validate(raw, sources=sources) == value
    with pytest.raises(a.c.ContractError, match="SOURCE_COMMAND"):
        a.validate(raw, sources=replace(sources, remote_tokens=["different fixed tokens"]))
    with pytest.raises(a.c.ContractError, match="SOURCE_POLICY_PIN"):
        a.validate(raw, sources=replace(sources, policy_sources=dict(sources.policy_sources, known_hosts=b"other")))
    # Source-less validation is an artifact check, not source authenticity.
    changed = copy.deepcopy(value)
    key = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + b"y" * 32
    item = changed["policy_basis"]["policies"]["authorized_keys"]
    item["predicate"]["parameters"]["approved_key"]["key_base64"] = base64.b64encode(key).decode()
    item["predicate_sha256"] = a._hash(item["predicate"])
    changed["policy_basis"]["policy_predicates_sha256"] = a._hash(changed["policy_basis"]["policies"])
    raw = a.c.canonical(changed, newline=True)
    assert a.validate(raw) == changed
    with pytest.raises(a.c.ContractError, match="SOURCE_POLICY_KEY"):
        a.validate(raw, sources=sources)


def test_builder_runs_second_source_path_automatically_and_does_not_mutate_inputs(artifact, monkeypatch):
    value, sources = source_fixture(artifact, monkeypatch)
    capacity = value["historical_capacity_obligations"]
    # These three raw-reading transforms have their own fixed-pin tests. This
    # synthetic aggregate test checks their complete result wiring and the
    # independent comparison before bytes can leave the builder.
    monkeypatch.setattr(a.horizon, "build_horizon", lambda _raw: {
        key: copy.deepcopy(capacity[key]) for key in ("snapshot_rows", "delta_rows", "effective_rows",
                                                     "row_relation", "configured_quota_rows", "totals")})
    before = copy.deepcopy(value)
    calls = []
    original = a._verify_sources
    def checked(parsed, held):
        calls.append(held)
        return original(parsed, held)
    monkeypatch.setattr(a, "_verify_sources", checked)
    raw = a.build(sources=sources)
    assert a.c.document(raw, limit=a.LIMIT, newline=True) == before
    assert value == before and calls == [sources]


def historical_loader_fixture(monkeypatch):
    """Synthetic trusted historical Git closure, different from today's files."""
    verifier = b'''import importlib.util
from pathlib import PurePosixPath as Path
def helper():
    spec = importlib.util.spec_from_file_location("_old_approved_contract", Path(__file__).with_name("q2_reconciliation_contract.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
contract = helper()
def verify(manifest, digest, blobs, *, implementation_commit):
    if blobs.get("raise"):
        raise ValueError("synthetic verification failed")
    return dict(value=contract.HISTORICAL_VALUE, module_path=contract.__file__, commit=implementation_commit)
if __name__ == "__main__":
    raise AssertionError("historical batch entry must not run")
'''
    tools = {"q2_fixture_" + str(index) + ".py": b"# unused pinned member\n" for index in range(38)}
    tools.update(q2_reconciliation_sources=verifier)  # converted to .py below
    tools["q2_reconciliation_sources.py"] = tools.pop("q2_reconciliation_sources")
    tools["q2_reconciliation_contract.py"] = b'HISTORICAL_VALUE = "from-retained-Git-bytes"\n'
    tools["q2_startup_retry.py"] = b"# pinned producer, no execution entry\n"
    tools["q2_reconciliation_billing.py"] = b"# pinned billing, no execution entry\n"
    hashes = {"/synthetic/legacy/tools/" + name: hashlib.sha256(raw).hexdigest() for name, raw in tools.items()}
    manifest = a.c.canonical(dict(execution=dict(source=dict(commit=a.legacy.LEGACY_COMMIT,
                                        tree=a.legacy.LEGACY_TREE, files=hashes))), newline=True)
    monkeypatch.setattr(a.legacy, "MANIFEST_PIN", (len(manifest), hashlib.sha256(manifest).hexdigest()))
    monkeypatch.setattr(a, "LEGACY_BLOBS", {role: hashlib.sha1(b"blob " + str(len(tools["q2_" + role + ".py"])).encode()
        + b"\0" + tools["q2_" + role + ".py"]).hexdigest() for role in a.LEGACY_BLOBS})
    return manifest, tools


def test_historical_ram_loader_uses_pinned_siblings_instead_of_current_checkout(monkeypatch):
    manifest, tools = historical_loader_fixture(monkeypatch)
    current = Path(a.__file__).with_name("q2_reconciliation_contract.py").read_bytes()
    assert current != tools["q2_reconciliation_contract.py"]
    original_hook = importlib.util.spec_from_file_location
    result = a._run_legacy_verifier(manifest, {}, tools)
    assert result == dict(value="from-retained-Git-bytes",
                          module_path="/synthetic/legacy/tools/q2_reconciliation_contract.py",
                          commit=a.legacy.LEGACY_COMMIT)
    assert importlib.util.spec_from_file_location is original_hook
    with pytest.raises(ValueError, match="synthetic verification failed"):
        a._run_legacy_verifier(manifest, {"raise": True}, tools)
    assert importlib.util.spec_from_file_location is original_hook


def test_historical_ram_loader_rejects_changed_manifest_and_changed_source_before_execution(monkeypatch):
    manifest, tools = historical_loader_fixture(monkeypatch)
    with pytest.raises(a.c.ContractError, match="LEGACY_MANIFEST_PIN"):
        a._run_legacy_verifier(manifest + b" ", {}, tools)
    changed = dict(tools)
    changed["q2_reconciliation_contract.py"] = b'raise AssertionError("must not execute changed source")\n'
    with pytest.raises(a.c.ContractError, match="LEGACY_TOOL_DIGEST"):
        a._run_legacy_verifier(manifest, {}, changed)
    changed.pop("q2_reconciliation_contract.py")
    with pytest.raises(a.c.ContractError, match="LEGACY_TOOL_CLOSURE"):
        a._run_legacy_verifier(manifest, {}, changed)
