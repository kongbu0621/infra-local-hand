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

    def test_manifest_directory_close_failure_attempts_every_descriptor_once(self):
        import stat
        root = self.root / "payload"; root.mkdir()
        nested = root / "nested"; nested.mkdir()
        (nested / "data").write_bytes(b"approved")
        manifest = {"nested/data": hashlib.sha256(b"approved").hexdigest()}
        actual_open, actual_close = os.open, os.close
        opened, attempts = [], []
        def tracked_open(*args, **kwargs):
            descriptor = actual_open(*args, **kwargs)
            if stat.S_ISDIR(os.fstat(descriptor).st_mode): opened.append(descriptor)
            return descriptor
        def failed_first_directory_close(descriptor):
            if descriptor in opened:
                attempts.append(descriptor)
                actual_close(descriptor)
                if len(attempts) == 1: raise OSError("directory close acknowledgement unavailable")
            else:
                actual_close(descriptor)
        try:
            with patch.object(os, "open", side_effect=tracked_open), \
                    patch.object(os, "close", side_effect=failed_first_directory_close):
                try:
                    jobs.verify_manifest(root, manifest)
                except Exception as error:
                    observed_error = error
                else:
                    self.fail("uncertain descriptor close unexpectedly succeeded")
            print(json.dumps({"directory_descriptors": len(opened), "close_attempts": len(attempts),
                              "error": type(observed_error).__name__}, sort_keys=True))
            self.assertEqual(attempts, list(reversed(opened)))
            self.assertEqual(len(set(attempts)), len(attempts))
            self.assertIsInstance(observed_error, jobs.LedgerPlanError)
            self.assertEqual((nested / "data").read_bytes(), b"approved")
            # A simultaneous validation failure retains its original meaning,
            # while the same close failure still cannot skip the other FDs.
            opened.clear(); attempts.clear()
            with patch.object(os, "open", side_effect=tracked_open), \
                    patch.object(os, "close", side_effect=failed_first_directory_close):
                with self.assertRaisesRegex(jobs.LedgerPlanError, "input byte binding mismatch") as failed:
                    jobs.verify_manifest(root, {"nested/data": "0" * 64})
            self.assertEqual(attempts, list(reversed(opened)))
            self.assertEqual(failed.exception.__notes__, ["input inventory descriptor cleanup was incomplete"])
        finally:
            for descriptor in opened:
                try: os.fstat(descriptor)
                except OSError: continue
                actual_close(descriptor)

    def test_temp_fallback_fails_and_does_not_count_as_binding(self):
        good = self.root / "tmp"; good.mkdir()
        with patch.dict(os.environ, {"TMPDIR": str(good), "TMP": str(good), "TEMP": str(good)}, clear=True):
            self.assertEqual(jobs.check_temp_binding(str(good))["temporary"], str(good))
            with patch.object(tempfile, "gettempdir", return_value=str(self.root)):
                with self.assertRaises(jobs.LedgerPlanError): jobs.check_temp_binding(str(good))
        with self.assertRaises(jobs.LedgerPlanError): jobs.check_temp_binding(str(self.root / "absent"))
        tempfile.tempdir = None

    def test_manifest_cleanup_failure_is_not_hidden_by_a_callers_handled_error(self):
        import stat
        root = self.root / "ambient-payload"; root.mkdir()
        (root / "data").write_bytes(b"approved")
        manifest = {"data": hashlib.sha256(b"approved").hexdigest()}
        actual_close = os.close
        def failed_directory_close(descriptor):
            directory = stat.S_ISDIR(os.fstat(descriptor).st_mode)
            actual_close(descriptor)
            if directory: raise OSError("directory close acknowledgement unavailable")
        try:
            raise LookupError("unrelated caller recovery")
        except LookupError as ambient:
            with patch.object(os, "close", side_effect=failed_directory_close):
                with self.assertRaises(jobs.LedgerPlanError):
                    jobs.verify_manifest(root, manifest)
            self.assertFalse(hasattr(ambient, "__notes__"))
        self.assertEqual((root / "data").read_bytes(), b"approved")

    def test_temp_probe_short_write_cannot_confirm_binding(self):
        root = self.root / "short-write"; root.mkdir()
        actual_write = os.write
        for count in (0, 1, len(b"lh-temp-binding\n") - 1):
            with self.subTest(count=count):
                def short_write(descriptor, data):
                    return actual_write(descriptor, data[:count])
                with patch.object(tempfile, "gettempdir", return_value=str(root)), \
                        patch.object(os, "write", side_effect=short_write):
                    with self.assertRaises(jobs.LedgerPlanError):
                        jobs.check_temp_binding(str(root))
                self.assertEqual(list(root.iterdir()), [])

    def test_temp_probe_close_failure_still_removes_owned_probe(self):
        root = self.root / "close-failure"; root.mkdir()
        actual_close = os.close
        closed = []
        def close_then_fail(descriptor):
            closed.append(descriptor)
            actual_close(descriptor)
            raise OSError("probe close acknowledgement unavailable")
        try:
            raise LookupError("unrelated caller recovery")
        except LookupError as ambient:
            with patch.object(tempfile, "gettempdir", return_value=str(root)), \
                    patch.object(os, "close", side_effect=close_then_fail):
                with self.assertRaisesRegex(OSError, "probe close acknowledgement unavailable"):
                    jobs.check_temp_binding(str(root))
            self.assertFalse(hasattr(ambient, "__notes__"))
        # Both the probe and its retained parent descriptor are released once.
        self.assertEqual(len(closed), 2)
        self.assertEqual(len(set(closed)), 2)
        self.assertEqual(list(root.iterdir()), [])
        with self.assertRaises(OSError): os.fstat(closed[0])

    def test_temp_probe_primary_failure_survives_failed_close(self):
        root = self.root / "sync-failure"; root.mkdir()
        actual_close = os.close
        primary = OSError("probe sync failed")
        def close_then_fail(descriptor):
            actual_close(descriptor)
            raise OSError("probe close acknowledgement unavailable")
        with patch.object(tempfile, "gettempdir", return_value=str(root)), \
                patch.object(os, "fsync", side_effect=primary), \
                patch.object(os, "close", side_effect=close_then_fail):
            try:
                jobs.check_temp_binding(str(root))
            except OSError as error:
                observed = error
            else:
                self.fail("failed temporary write probe unexpectedly succeeded")
        self.assertIs(observed, primary)
        self.assertEqual(list(root.iterdir()), [])
        self.assertEqual(primary.__notes__, ["temporary probe cleanup was incomplete"])

    def test_temp_probe_is_anonymous_and_cannot_unlink_concurrent_file(self):
        root = self.root / "probe-swap"; root.mkdir()
        actual_fsync = os.fsync
        replacement = root / "concurrent-owner"
        def replace_probe(descriptor):
            actual_fsync(descriptor)
            self.assertEqual(os.fstat(descriptor).st_nlink, 0)
            self.assertEqual(list(root.iterdir()), [])
            replacement.write_bytes(b"concurrent-owner-data")
        with patch.object(tempfile, "gettempdir", return_value=str(root)), \
                patch.object(os, "fsync", side_effect=replace_probe), \
                patch.object(os, "unlink", side_effect=AssertionError("anonymous probe must not unlink")):
            result = jobs.check_temp_binding(str(root))
        self.assertEqual(result["inode"], root.stat().st_ino)
        self.assertEqual(replacement.read_bytes(), b"concurrent-owner-data")

    def test_temp_probe_replaced_directory_cannot_bind_or_delete_replacement(self):
        for mutation in ("before-create", "after-write"):
            with self.subTest(mutation=mutation):
                root = self.root / mutation; root.mkdir()
                detached = self.root / (mutation + "-retained")
                opened, synced = os.open, os.fsync
                replacement = None
                def replace_directory():
                    nonlocal replacement
                    root.rename(detached); root.mkdir()
                    replacement = root / "concurrent-owner"
                    replacement.write_bytes(b"concurrent-owner-data")
                def open_probe(path, flags, *args, **kwargs):
                    if flags & os.O_TMPFILE == os.O_TMPFILE:
                        replace_directory()
                    return opened(path, flags, *args, **kwargs)
                def sync_probe(descriptor):
                    synced(descriptor)
                    replace_directory()
                with patch.object(tempfile, "gettempdir", return_value=str(root)), \
                        patch.object(os, "open", side_effect=open_probe if mutation == "before-create" else opened), \
                        patch.object(os, "fsync", side_effect=sync_probe if mutation == "after-write" else synced):
                    with self.assertRaisesRegex(jobs.LedgerPlanError, "root changed"):
                        jobs.check_temp_binding(str(root))
                self.assertEqual(replacement.read_bytes(), b"concurrent-owner-data")
                self.assertEqual(list(detached.iterdir()), [])

    def test_temp_probe_unsupported_anonymous_inode_never_uses_named_fallback(self):
        import errno
        root = self.root / "anonymous-unavailable"; root.mkdir()
        original_open = os.open
        opened = []
        def reject_anonymous(path, flags, *args, **kwargs):
            self.assertFalse(flags & os.O_CREAT, "named fallback must not be attempted")
            if flags & os.O_TMPFILE == os.O_TMPFILE:
                raise OSError(errno.EOPNOTSUPP, "fixture anonymous files unavailable")
            descriptor = original_open(path, flags, *args, **kwargs)
            opened.append(descriptor)
            return descriptor
        with patch.object(tempfile, "gettempdir", return_value=str(root)), \
                patch.object(os, "open", side_effect=reject_anonymous):
            with self.assertRaisesRegex(jobs.LedgerPlanError, "anonymous temporary probe is unavailable"):
                jobs.check_temp_binding(str(root))
        self.assertEqual(len(opened), 1)
        with self.assertRaises(OSError): os.fstat(opened[0])
        with patch.object(tempfile, "gettempdir", return_value=str(root)), \
                patch.object(os, "O_TMPFILE", None):
            with self.assertRaisesRegex(jobs.LedgerPlanError, "anonymous temporary probe is unsupported"):
                jobs.check_temp_binding(str(root))
        self.assertEqual(list(root.iterdir()), [])

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

    def test_regular_reads_reject_incomplete_bytes_even_when_metadata_is_stable(self):
        path = self.root / "complete-result.json"
        prefix = b'{"outcome":"SUCCEEDED"}'
        raw = prefix + b" CORRUPTED SUFFIX"
        path.write_bytes(raw)
        readers = (jobs._regular_bytes, lambda path: jobs.bounded_regular_bytes(path, 1024))
        for reader in readers:
            with self.subTest(reader=reader.__name__):
                for chunks in ([prefix, b""], [b""], [raw + b"EXTRA", b""]):
                    with patch.object(os, "read", side_effect=chunks):
                        with self.assertRaises(jobs.LedgerPlanError): reader(path)
                # Multiple legitimate short reads are complete once their bytes
                # match the unchanged descriptor size; do not require one read.
                with patch.object(os, "read", side_effect=[raw[:3], raw[3:], b""]):
                    self.assertEqual(reader(path), raw)

    def test_regular_read_cleanup_preserves_primary_error_and_closes_once(self):
        path = self.root / "read-cleanup"; path.write_bytes(b"input")
        readers = (jobs._regular_bytes, lambda path: jobs.bounded_regular_bytes(path, 1024))
        actual_close = os.close
        for reader in readers:
            for failure in (OSError("input read failed"), KeyboardInterrupt("read interrupted"), None):
                with self.subTest(reader=reader.__name__, failure=type(failure).__name__):
                    closed = []
                    cleanup_error = OSError("close acknowledgement missing")
                    def close_then_fail(descriptor):
                        closed.append(descriptor)
                        actual_close(descriptor)
                        raise cleanup_error
                    with patch.object(os, "close", side_effect=close_then_fail), \
                            patch.object(os, "read", side_effect=failure if failure is not None else [b"input", b""]):
                        with self.assertRaises(BaseException) as observed: reader(path)
                    self.assertIs(observed.exception, failure if failure is not None else cleanup_error)
                    if failure is not None:
                        self.assertIn("input descriptor cleanup was incomplete", failure.__notes__)
                    self.assertEqual(len(closed), 1)
                    with self.assertRaises(OSError): os.fstat(closed[0])

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
