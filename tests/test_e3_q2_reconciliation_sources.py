"""Synthetic provenance/authority boundaries; never a guest admission claim."""
import copy
import importlib.util
from pathlib import Path, PurePosixPath as P
import stat
import sys
from types import SimpleNamespace
import unittest

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest("Inherited synthetic Q2 contracts use Linux paths")

from test_e3_q2_startup_retry_contract import fixture as startup_fixture

spec = importlib.util.spec_from_file_location("_reconciliation_sources_test",
    Path(__file__).parent / "e3_host/q2_reconciliation_sources.py")
s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
c = s.c


def manifest_fixture():
    original, previous, old = startup_fixture()
    execution = {key: copy.deepcopy(old[key]) for key in c.EXECUTION_FIELDS}
    previous_bound = c.old.legacy.bind(original, previous)
    current_paths = {
        "second-bootstrap-intent": str(P(previous_bound["candidate"]["source"]).parent) + ".intent.json",
        "second-bootstrap-attestation": str(P(previous_bound["candidate"]["source"]).parent / "bootstrap-attestation.json"),
    }
    for name in c.REQUIRED_SOURCE_FILES:
        execution["source"]["files"]["/synthetic/startup-tools/" + name] = "f" * 64
    sources = []
    for index, (name, pin) in enumerate(sorted(execution["old_files"].items())):
        role = next((role for role, current in current_paths.items() if current == name), None)
        if role:
            digest, length = c.CURRENT_RAW[role]
            sources.append(dict(id=role, path=name, sha256=digest, bytes=length,
                source_class="CURRENT_OWNER_SUPPLIED_RAW", proof_id="owner-adoption"))
            del execution["old_files"][name]
        else:
            sources.append(dict(id="historical-%d" % index, path=name, sha256=pin, bytes=10,
                source_class="HISTORICAL_PIN", proof_id="history-pin"))
    manifest = dict(schema=c.SCHEMA, scope=c.SCOPE, rule=c.RULE, baseline=c.BASELINE, closure=c.CLOSURE,
        owner_decision=c.OWNER_DECISION, implementation_commit=execution["source"]["commit"],
        operation_id="synthetic-reconciliation", startup_authority=dict(baseline=c.old.BASELINE,
            closure=c.old.CLOSURE, owner_decision=c.old.OWNER_DECISION),
        original_plan=dict(path=execution["original_plan_path"], sha256=execution["original_plan_sha256"],
            bytes=len(c.c.encoded(original))),
        previous_plan=dict(path=execution["predecessors"][1]["plan_path"],
            sha256=execution["predecessors"][1]["plan_sha256"], bytes=len(c.c.encoded(previous))),
        execution=execution, sources=sources,
        evidence={role: dict(sha256=pin, bytes=length) for role, (pin, length) in c.EVIDENCE.items()})
    return original, previous, manifest


def decode(value):
    raw = c.encoded(value)
    return c.decode(raw, c.sha(raw), implementation_commit="c" * 40)


def entry(path, inode, *, directory=False, content=b"sample", sparse=False):
    metadata = dict(path=path, type="directory" if directory else "regular", device=1, inode=inode,
        st_mode=(stat.S_IFDIR | 0o700) if directory else (stat.S_IFREG | 0o600), uid=0, gid=0,
        nlink=2 if directory else 1, size=4096 if directory else len(content),
        blocks=0 if sparse else 8, atime_ns=100, mtime_ns=200, ctime_ns=300)
    return dict(source_metadata=metadata, sha256=None if directory else c.sha(content))


def scan(root, rows):
    result = []
    for row in rows:
        meta = row["source_metadata"]; relative = "." if meta["path"] == root else str(P(meta["path"]).relative_to(root))
        item = dict(relative_path=relative, type="file" if meta["type"] == "regular" else meta["type"],
            source_metadata={key: meta[key] for key in s.META_FIELDS})
        if row["sha256"] is not None: item["sha256"] = row["sha256"]
        result.append(item)
    return dict(path=root, entries=result, inodes=len(result), device=rows[0]["source_metadata"]["device"],
        logical_bytes=sum(row["source_metadata"]["size"] for row in rows if row["source_metadata"]["type"] == "regular"),
        bytes=sum(row["source_metadata"]["blocks"] * 512 for row in rows))


def live_fixture():
    trees, scans, raw, classes = [], {}, {}, {}
    for index in range(12):
        root = "/synthetic/historical-%02d" % index
        rows = [entry(root, 10 + index, content=b"sample")]
        trees.append(s.historical_snapshot(root, rows)); scans[root] = scan(root, rows)
        raw[root] = b"sample"; classes[root] = "HISTORICAL_TREE_MEMBER"
    root = "/synthetic/current-stage"; intent = root + ".intent.json"
    forward = [entry(root, 100, directory=True), entry(intent, 101)]
    forward += [entry(root + "/file-%04d" % i, 102 + i) for i in range(608)]
    forward.sort(key=lambda row: row["source_metadata"]["path"])
    scans[root] = scan(root, [row for row in forward if row["source_metadata"]["path"] != intent])
    scans[intent] = scan(intent, [next(row for row in forward if row["source_metadata"]["path"] == intent)])
    baseline = dict(root=root, adjacent_intent=intent, sha256=c.EVIDENCE["forward_baseline"][0], entries=forward)
    metadata = {}
    for name in sorted(raw)[:5]:
        metadata[name] = dict(sha256=c.sha(raw[name]), source_metadata=scans[name]["entries"][0]["source_metadata"],
            historical_atime_preservation_proven=False)
    verified = SimpleNamespace(historical_trees=tuple(trees), forward_baseline=baseline,
        metadata_baselines=metadata, raw_by_path=raw, source_classes=classes)
    return verified, scans


class ReconciliationContractTests(unittest.TestCase):
    def test_new_binding_preserves_old_bytes_and_does_not_create_legacy_authority(self):
        original, previous, manifest = manifest_fixture(); before = copy.deepcopy((original, previous, manifest))
        checked = decode(manifest)
        execution, plan, historical = c.bind(checked, original, previous)
        self.assertEqual(c.SCHEMA, execution["schema"])
        self.assertEqual(c.SCOPE, plan["scope"])
        self.assertEqual(140, plan["budgets"]["preparation_seconds"])
        self.assertEqual(c.old.CANDIDATE_COMMIT, plan["candidate"]["commit"])
        self.assertEqual(before, (original, previous, manifest))
        for row in manifest["sources"]:
            if row["source_class"] == "CURRENT_OWNER_SUPPLIED_RAW":
                self.assertNotIn(row["path"], execution["old_files"])
        with self.assertRaises(ValueError):
            c.old.decode(c.encoded(execution), c.sha(c.encoded(execution)))
        manifest["operation_id"] = manifest["execution"]["attempt_id"]
        with self.assertRaisesRegex(ValueError, "RECONCILIATION_OPERATION_ID_REUSE"):
            c.bind(decode(manifest), original, previous)

    def test_duplicate_keys_float_boolean_overflow_negative_are_rejected(self):
        cases = (b'{"x":1,"x":2}', b'{"x":1.0}', b'{"x":NaN}', b'{"x":Infinity}',
            b'{"x":-1}', b'{"x":9223372036854775808}', b'\xff', b'[' * 2000)
        for raw in cases:
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError): c.document(raw)
        for value in (True, False, 1.0, -1, 2**63):
            with self.subTest(value=value), self.assertRaises(ValueError): c.number(value)

    def test_exact_authority_source_classes_and_no_third_adoption(self):
        for mutate in (
            lambda m: m.update(closure="0" * 40),
            lambda m: m.update(baseline=c.old.BASELINE),
            lambda m: m.update(released=True),
            lambda m: m["startup_authority"].update(closure="0" * 40),
            lambda m: m["sources"][0].update(proof_id="unknown", source_class="UNVERIFIED"),
            lambda m: m["sources"].append(dict(m["sources"][0], id="third-source", path="/synthetic/third")),
            lambda m: m["evidence"]["forward_baseline"].update(sha256="a" * 64),
        ):
            _, _, manifest = manifest_fixture(); mutate(manifest)
            with self.assertRaises(ValueError): decode(manifest)

    def test_current_values_cannot_be_laundered_into_historical_pins(self):
        for action in ("class", "old-files", "digest", "remove"):
            _, _, manifest = manifest_fixture()
            current = next(row for row in manifest["sources"] if row["source_class"] == "CURRENT_OWNER_SUPPLIED_RAW")
            if action == "class": current.update(source_class="HISTORICAL_PIN", proof_id="history-pin")
            elif action == "old-files": manifest["execution"]["old_files"][current["path"]] = current["sha256"]
            elif action == "digest": current["sha256"] = "0" * 64
            else: manifest["sources"].remove(current)
            with self.subTest(action=action), self.assertRaises(ValueError): decode(manifest)

    def test_limits_reference_alias_and_explicit_d_pin(self):
        for mutate in (
            lambda m: m["sources"][0].update(bytes=1024**2 + 1),
            lambda m: m["sources"][0].update(bytes=True),
            lambda m: m["sources"][0].update(path="/synthetic/../alias"),
            lambda m: m["sources"][0].update(id="a" * 129),
            lambda m: m["execution"]["source"].update(commit=c.CLOSURE),
            lambda m: m["execution"]["source"]["files"].pop("/synthetic/startup-tools/q2_reconciliation_sources.py"),
        ):
            _, _, manifest = manifest_fixture(); mutate(manifest)
            with self.assertRaises(ValueError): decode(manifest)
        _, _, manifest = manifest_fixture(); raw = c.encoded(manifest)
        with self.assertRaises(ValueError): c.decode(raw, c.sha(raw), implementation_commit="a" * 40)
        for name in c.REQUIRED_SOURCE_FILES:
            _, _, manifest = manifest_fixture()
            del manifest["execution"]["source"]["files"]["/synthetic/startup-tools/" + name]
            with self.subTest(missing=name), self.assertRaises(ValueError): decode(manifest)


class ReconciliationProofTests(unittest.TestCase):
    def test_current_tree_cannot_replace_history_expand_scope_or_hide_member_changes(self):
        verified, _ = live_fixture(); rows = verified.forward_baseline["entries"]
        entries = {row["source_metadata"]["path"]: row for row in rows}
        second = dict(candidate=dict(source="/synthetic/current-stage/source"))
        value = dict(schema="q2-return-forward-comparison-evidence/v1", scope="future comparison only",
            source_archive_sha256=c.ARCHIVE_SHA256, guest_manifest_sha256=c.EVIDENCE["guest_manifest"][0],
            proposed_only=True, historical_identity_claim=False, entries=copy.deepcopy(rows))
        self.assertEqual(610, len(s._forward(value, entries, second)["entries"]))
        for mutate in (lambda x: x.update(historical_identity_claim=True),
            lambda x: x.update(proposed_only=False), lambda x: x.update(source_archive_sha256="0" * 64),
            lambda x: x["entries"].pop(), lambda x: x["entries"][3].update(sha256="0" * 64),
            lambda x: x["entries"][3]["source_metadata"].update(inode=99999)):
            changed = copy.deepcopy(value); mutate(changed)
            with self.assertRaises(ValueError): s._forward(changed, entries, second)
        with self.assertRaises(ValueError): s._forward(value, entries,
            dict(candidate=dict(source="/synthetic/another-stage/source")))

    def test_only_exact_five_post_read_rows_are_adopted_and_initial_stat_is_not_invented(self):
        original = dict(candidate=dict(source="/synthetic/original-stage/source"))
        second = dict(candidate=dict(source="/synthetic/current-stage/source"))
        execution = dict(predecessors=[dict(prepared_path="/synthetic/recovery/prepared.json")],
            reservations=[dict(kind="RECOVERY_STAGE", path="/synthetic/recovery-stage/tools/stage.json")])
        names = ("/synthetic/original-stage.intent.json", "/synthetic/current-stage.intent.json",
            "/synthetic/recovery/recovery-intent.json", "/synthetic/recovery-stage/tools/stage.json",
            "/synthetic/current-stage/bootstrap-attestation.json")
        entries = {name: entry(name, index + 1) for index, name in enumerate(names)}
        files = [dict(path=name, atime_changed_during_preliminary_unprotected_hash_probe=True,
            **{"post_probe_" + key: entries[name]["source_metadata"][key]
                for key in ("atime_ns", "mtime_ns", "ctime_ns", "inode", "size")}) for name in names]
        note = dict(schema="local-hand-q2-collection-metadata-note/v1", event="No initial stat transcript",
            files=files, instruction_met_for_atime=False, instruction_met_for_content_mtime_ctime_identity=True)
        post = s._post_read(note, entries, original, second, execution)
        self.assertEqual(set(names), set(post))
        self.assertTrue(all(row["historical_atime_preservation_proven"] is False for row in post.values()))
        for mutate in (lambda x: x["files"].pop(), lambda x: x["files"].append(copy.deepcopy(x["files"][0])),
            lambda x: x["files"][0].update(path="/synthetic/prepare/preflight.json"),
            lambda x: x["files"][0].update(post_probe_atime_ns=1),
            lambda x: x.update(instruction_met_for_atime=True)):
            changed = copy.deepcopy(note); mutate(changed)
            with self.assertRaises(ValueError): s._post_read(changed, entries, original, second, execution)

    def test_original_tree_algorithm_and_sparse_charge_are_recomputed(self):
        root = "/synthetic/tree"; rows = [entry(root, 1, directory=True), entry(root + "/file", 2, content=b"x" * 5000, sparse=True)]
        value = s.historical_snapshot(root, rows)
        self.assertEqual(9096, value["bytes"])
        self.assertEqual(9096, value["logical_bytes"])
        self.assertEqual(value, s.compare_historical_tree(value, copy.deepcopy(rows)))
        changed = copy.deepcopy(rows); changed[1]["source_metadata"]["atime_ns"] += 1
        self.assertEqual(value, s.historical_snapshot(root, changed))  # old algorithm excluded atime
        for mutate in (
            lambda a: a.pop(), lambda a: a[1].update(sha256="0" * 64),
            lambda a: a[1]["source_metadata"].update(ctime_ns=999),
            lambda a: a[1]["source_metadata"].update(inode=1),
            lambda a: a[1]["source_metadata"].update(nlink=2),
            lambda a: a[1]["source_metadata"].update(device=2),
        ):
            changed = copy.deepcopy(rows); mutate(changed)
            with self.assertRaises(ValueError): s.compare_historical_tree(value, changed)

    def test_live_requires_every_original_tree_forward_member_source_and_post_value(self):
        verified, scans = live_fixture()
        result = s.verify_live_sources(verified, scans)
        self.assertEqual(610, result["forward_entries"])
        self.assertEqual(12, len(result["historical_trees"]))
        self.assertFalse(result["historical_atime_preservation_proven"])
        changes = (
            lambda a: a.pop("/synthetic/historical-00"),
            lambda a: a["/synthetic/current-stage"]["entries"].pop(),
            lambda a: a["/synthetic/current-stage"]["entries"][2].update(sha256="0" * 64),
            lambda a: a["/synthetic/current-stage"]["entries"][2]["source_metadata"].update(atime_ns=101),
            lambda a: a["/synthetic/historical-00"]["entries"][0]["source_metadata"].update(atime_ns=101),
            lambda a: a["/synthetic/historical-10"]["entries"][0]["source_metadata"].update(mtime_ns=201),
            lambda a: a["/synthetic/current-stage"]["entries"][1].update(relative_path="../escape"),
            lambda a: a["/synthetic/historical-10"].update(unknown_scan_field=True),
            lambda a: a["/synthetic/historical-10"]["entries"][0].update(unexpected_entry=True),
            lambda a: a["/synthetic/historical-10"]["entries"][0]["source_metadata"].update(unknown_field="accepted?"),
            lambda a: a["/synthetic/historical-10"].update(bytes=0),
            lambda a: a["/synthetic/historical-10"].update(logical_bytes=0),
            lambda a: a["/synthetic/historical-10"].update(device=2),
        )
        for mutate in changes:
            current = copy.deepcopy(scans); mutate(current)
            with self.assertRaises(ValueError): s.verify_live_sources(verified, current)

    def test_pinned_blob_total_parse_budget_and_missing_changed_bytes(self):
        raw = b'{"value":1}\n'; pin = c.sha(raw)
        reader = s._Inputs({pin: raw}, c.PARSED_TOTAL_LIMIT - len(raw))
        ref = dict(sha256=pin, bytes=len(raw))
        self.assertEqual({"value": 1}, reader.document(ref))
        self.assertEqual({"value": 1}, reader.document(ref))  # unique bytes charged once
        with self.assertRaises(ValueError): s._Inputs({pin: raw}, c.PARSED_TOTAL_LIMIT).document(ref)
        with self.assertRaises(ValueError): s._Inputs({}, 0).document(ref)
        with self.assertRaises(ValueError): s._Inputs({pin: b" " * len(raw)}, 0).document(ref)
        with self.assertRaises(ValueError): reader.raw(pin, len(raw) + 1)


if __name__ == "__main__":
    unittest.main()
