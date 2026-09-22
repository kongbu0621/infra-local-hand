"""Fixed-template and byte-binding tests use synthetic local inputs only."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from local_hand_jobs import ledger_jobs as jobs


def budget():
    return dict(wall_seconds=30, terminate_grace_seconds=2, cpu_seconds=10,
                memory_bytes=64 * 1024**2, processes=16, temporary_bytes=8 * 1024**2,
                nas_bytes=8 * 1024**2, log_bytes=32768, reservation_bytes=32 * 1024**2)


def profile(root):
    return dict(work_root=str(root / "work"), evidence_root=str(root / "evidence"),
                temporary_root=str(root / "temp"), python=sys.executable, budgets=budget(),
                source={"root": str(root / "admitted-source"), "commit": jobs.SOURCE_COMMIT,
                        "blobs": dict(jobs.SCRIPT_BLOBS)},
                build_cache={"root": str(root / "cache"), "files": {"x": "a" * 64}},
                storage={"config": str(root / "storage.json"), "config_digest": "a" * 64,
                         "archive_root": str(root / "archive"), "stable_mount_binding": True})


def prepared(root):
    return dict(root=str(root / "prepared"), source_root=str(root / "prepared/source"),
                build_python=str(root / "prepared/build-venv/bin/python"),
                runtime_python=str(root / "prepared/runtime-venv/bin/python"),
                wheel=str(root / "prepared/wheels/ledger.whl"), source_commit=jobs.SOURCE_COMMIT)


def request(kind, suite=None):
    inputs = {"prepared_ref": "prepared-fixture"} if kind not in ("host.inspect", "ledger.prepare") else {}
    if suite: inputs["suite"] = suite
    return dict(kind=kind, operation_id="00000000-0000-4000-8000-000000000001", inputs=inputs)


class LedgerPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = profile(self.root)
        self.prepared = prepared(self.root)

    def plan(self, kind, suite=None):
        mapping = dict(self.profile)
        if kind != "ledger.nas.roundtrip": mapping.pop("storage", None)
        if kind != "ledger.prepare":
            mapping.pop("source", None); mapping.pop("build_cache", None)
        return jobs.build_plan(request(kind, suite), mapping, self.prepared)

    def test_all_six_kinds_resolve_only_fixed_stage_templates(self):
        plans = {kind: self.plan(kind, "a1_resources" if kind == "ledger.test.resources" else None) for kind in jobs.KINDS}
        self.assertEqual(len(plans), 6)
        self.assertEqual([x["argv"][1:] for x in plans["ledger.test.source"]["stages"]], [
            ["-m", "unittest", "discover", "-s", "tests", "-v"],
            ["-m", "compileall", "-q", "src", "tests", "tools/acceptance"]])
        nas = plans["ledger.nas.roundtrip"]["stages"][0]
        self.assertEqual(nas["argv"][3::2], ["--local-parent", "--storage-config", "--source-commit", "--wheel"])
        self.assertEqual(len(nas["argv"]), 11)
        self.assertNotIn("PYTHONPATH", nas["env"])
        self.assertNotEqual(nas["cwd"], plans["ledger.nas.roundtrip"]["prepared"]["source_root"])

    def test_resource_direct_main_switch_and_a2_environment(self):
        for suite in jobs.SUITES:
            stage = self.plan("ledger.test.resources", suite)["stages"][0]
            self.assertEqual(stage["env"]["PYTHONPATH"], "src")
            if suite.startswith("a1_"):
                self.assertTrue(stage["argv"][1].startswith("tests/test_"))
                self.assertNotIn("A2_RESOURCE_TESTS", stage["env"])
            else:
                self.assertEqual(stage["env"]["A2_RESOURCE_TESTS"], "1")

    def test_preparation_uses_exact_offline_build_versions_and_original_venvs(self):
        plan = self.plan("ledger.prepare")
        stages = {x["name"]: x for x in plan["stages"]}
        self.assertTrue(set(jobs.BUILD_REQUIREMENTS) <= set(stages["install-build-cache"]["argv"]))
        self.assertIn("--no-index", stages["build-wheel"]["argv"])
        self.assertIn("--no-build-isolation", stages["build-wheel"]["argv"])
        self.assertIn("--no-deps", stages["install-wheel"]["argv"])
        self.assertIn("--copies", stages["create-runtime-venv"]["argv"])
        self.assertTrue(plan["prepared"]["runtime_python"].startswith(plan["roots"]["work"] + "/"))
        for stage in plan["stages"]:
            self.assertNotIn("GITHUB_TOKEN", stage["env"])
            self.assertEqual({stage["env"][key] for key in ("TMPDIR", "TMP", "TEMP")}, {plan["roots"]["temporary"]})

    def test_unknown_kind_suite_missing_budget_and_unstable_nas_rejected(self):
        with self.assertRaises(jobs.LedgerPlanError): self.plan("ledger.test.resources", "custom")
        with self.assertRaises(jobs.LedgerPlanError): self.plan("custom")
        for value in (None, True, -1, 0, float("inf")):
            self.profile["budgets"]["wall_seconds"] = value
            with self.assertRaises(jobs.LedgerPlanError): self.plan("host.inspect")
        self.profile["budgets"] = budget()
        self.profile["storage"]["stable_mount_binding"] = False
        with self.assertRaises(jobs.LedgerPlanError): self.plan("ledger.nas.roundtrip")

    def test_double_leading_separator_cannot_alias_admitted_plan_paths(self):
        for value in ("//fixture/work", "//fixture/python", "//fixture/prepared"):
            with self.subTest(value=value):
                with self.assertRaises(jobs.LedgerPlanError): jobs._path(value)
        for value in ("/fixture/work", "/fixture/python", "/fixture/prepared"):
            self.assertEqual(jobs._path(value), value)

    def test_replaced_bytes_extra_files_and_symlink_inputs_rejected(self):
        source = self.root / "source"; source.mkdir()
        path = source / "module.py"; path.write_bytes(b"trusted\n")
        manifest = {"module.py": hashlib.sha256(path.read_bytes()).hexdigest()}
        jobs.verify_manifest(source, manifest)
        path.write_bytes(b"replaced\n")
        with self.assertRaises(jobs.LedgerPlanError): jobs.verify_manifest(source, manifest)
        path.write_bytes(b"trusted\n")
        (source / "extra").write_text("extra")
        with self.assertRaises(jobs.LedgerPlanError): jobs.verify_manifest(source, manifest)
        (source / "extra").unlink(); path.unlink(); path.symlink_to(self.root / "outside")
        with self.assertRaises(OSError): jobs.verify_manifest(source, manifest)

    def test_git_name_does_not_hide_extra_cache_or_prepared_payload(self):
        root = self.root / "payload"; root.mkdir()
        (root / "allowed.py").write_bytes(b"approved")
        manifest = {"allowed.py": hashlib.sha256(b"approved").hexdigest()}
        hidden = root / ".git"; hidden.mkdir()
        (hidden / "unadmitted.py").write_bytes(b"extra bytes")
        with self.assertRaises(jobs.LedgerPlanError): jobs.verify_manifest(root, manifest)
        git_manifest = {"allowed.py": hashlib.sha1(b"blob 8\0approved").hexdigest()}
        # The exact source checkout root has an explicit Git metadata exception.
        jobs.verify_manifest(root, git_manifest, git_blobs=True)
        nested = root / "package"; nested.mkdir()
        (nested / ".git").mkdir()
        (nested / ".git" / "unadmitted.py").write_bytes(b"extra bytes")
        with self.assertRaises(jobs.LedgerPlanError): jobs.verify_manifest(root, git_manifest, git_blobs=True)

    def test_inventory_scan_error_is_not_an_empty_directory(self):
        root = self.root / "payload"; root.mkdir()
        (root / "allowed.py").write_bytes(b"approved")
        hidden = root / "unreadable"; hidden.mkdir()
        (hidden / "unadmitted.py").write_bytes(b"extra")
        manifest = {"allowed.py": hashlib.sha256(b"approved").hexdigest()}
        real = os.scandir
        def denied(path):
            matches = os.fstat(path).st_ino == hidden.stat().st_ino if isinstance(path, int) else Path(path) == hidden
            if matches: raise PermissionError("fixture scan denied")
            return real(path)
        with patch.object(os, "scandir", side_effect=denied):
            with self.assertRaises(jobs.LedgerPlanError): jobs.verify_manifest(root, manifest)

    def test_manifest_rejects_directory_swap_and_late_extra_member(self):
        for mutation in ("directory-swap", "extra-member"):
            with self.subTest(mutation=mutation):
                root = self.root / mutation; root.mkdir()
                child = root / "pkg"; child.mkdir()
                outside = self.root / (mutation + "-outside"); outside.mkdir()
                data = b"admitted payload"
                (child / "module.py").write_bytes(data)
                (outside / "module.py").write_bytes(data)
                manifest = {"pkg/module.py": hashlib.sha256(data).hexdigest()}
                read = jobs._regular_bytes
                injected = False
                def mutate_before_read(path, *args, **kwargs):
                    nonlocal injected
                    if Path(path).name == "module.py" and not injected:
                        injected = True
                        if mutation == "directory-swap":
                            child.rename(root / "detached")
                            child.symlink_to(outside, target_is_directory=True)
                        else:
                            (root / "late-extra.py").write_bytes(b"unadmitted")
                    return read(path, *args, **kwargs)
                with patch.object(jobs, "_regular_bytes", side_effect=mutate_before_read):
                    with self.assertRaises(jobs.LedgerPlanError): jobs.verify_manifest(root, manifest)
                self.assertTrue(injected)

    def test_copy_is_independent_and_exact_git_blob_checked(self):
        source = self.root / "source"; source.mkdir()
        data = b"print('fixture')\n"; (source / "main.py").write_bytes(data)
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        work = self.root / "copy-job"; work.mkdir()
        plan = {"kind": "ledger.test.source", "roots": {"work": str(work)},
                "prepared": {"source_root": str(source), "source_blobs": {"main.py": blob}}}
        jobs.copy_verified_source(plan)
        copied = work / "source/main.py"
        self.assertNotEqual(copied.stat().st_ino, (source / "main.py").stat().st_ino)
        copied.write_text("new local test product")
        self.assertEqual((source / "main.py").read_bytes(), data)

    def test_temp_fallback_fails_and_does_not_count_as_binding(self):
        good = self.root / "tmp"; good.mkdir()
        with patch.dict(os.environ, {"TMPDIR": str(good), "TMP": str(good), "TEMP": str(good)}, clear=True):
            self.assertEqual(jobs.check_temp_binding(str(good))["temporary"], str(good))
            with patch.object(tempfile, "gettempdir", return_value=str(self.root)):
                with self.assertRaises(jobs.LedgerPlanError): jobs.check_temp_binding(str(good))
        with self.assertRaises(jobs.LedgerPlanError): jobs.check_temp_binding(str(self.root / "absent"))
        tempfile.tempdir = None

    def test_resource_skips_and_wrong_counts_never_pass(self):
        for text in ("Ran 8 tests in 1s\n\nOK (skipped=1)\n", "Ran 7 tests in 1s\n\nOK\n", ""):
            self.assertEqual(jobs.resource_result("a1_resources", "", text, 0)["outcome"], "FAILED")
        self.assertEqual(jobs.resource_result("a1_resources", "", "Ran 8 tests in 1s\n\nOK\n", 0)["outcome"], "SUCCEEDED")
        self.assertEqual(jobs.resource_result("a1_resources", "", "Ran 8 tests in 1s\n\nOK\n", 0)["coverage"], "PASS")
        self.assertEqual(jobs.resource_result("a2_semantic_resources", "", "Ran 4 tests in 1s\n\nOK\n", 0)["coverage"], "LOGIC_ONLY")

    def test_bounded_read_rejects_size_before_consumption(self):
        path = self.root / "large"; path.write_bytes(b"x" * 100)
        with patch.object(os, "read", side_effect=AssertionError("must not read oversized input")):
            with self.assertRaises(jobs.LedgerPlanError): jobs.bounded_regular_bytes(path, 99)
        self.assertEqual(jobs.bounded_regular_bytes(path, 100), b"x" * 100)

    def test_bounded_read_rejects_a_replaced_named_entry(self):
        owned = self.root / "owned"; owned.mkdir()
        path = owned / "result.json"
        path.write_bytes(b'{"outcome":"SUCCEEDED"}')
        replacement = self.root / "replacement"; replacement.mkdir()
        (replacement / "result.json").write_bytes(b'{"outcome":"FAILED"}')
        original_read = os.read
        changed = False
        def replaced_after_read(descriptor, maximum):
            nonlocal changed
            raw = original_read(descriptor, maximum)
            if raw and not changed:
                changed = True
                # Directory replacement leaves the opened file's own metadata
                # untouched while changing the bytes at the claimed pathname.
                owned.rename(self.root / "detached")
                replacement.rename(owned)
            return raw
        with patch.object(os, "read", side_effect=replaced_after_read):
            with self.assertRaises(jobs.LedgerPlanError):
                jobs.bounded_regular_bytes(path, 1024)
        self.assertTrue(changed)
        self.assertEqual(path.read_bytes(), b'{"outcome":"FAILED"}')

    def test_missing_and_ambiguous_nas_stdout_recovery_remains_unknown(self):
        root = self.root / "exclusive"; root.mkdir()
        self.assertEqual(jobs.discover_nas_run(root)["outcome"], "UNKNOWN")
        for i in ("a", "b"):
            candidate = root / ("a2-nas-" + i * 32); candidate.mkdir()
            (candidate / "OWNED.json").write_text(json.dumps({"run_id": candidate.name}))
            (candidate / "snapshot-reference.json").write_text("{}")
        found = jobs.discover_nas_run(root)
        self.assertEqual(found["outcome"], "UNKNOWN")
        self.assertNotIn("run_id", found)


if __name__ == "__main__": unittest.main()
