"""Read-only batch checks with real local files and an in-memory SQLite review.

Host ownership ancestry, systemd, cgroup, namespace and source-loader authority
are explicitly modeled where noted. No tests start services or query/set quota.
"""
import contextlib
import copy
import errno
import hashlib
import importlib.util
import json
import marshal
import os
from pathlib import Path
import py_compile
import sqlite3
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

PATH = Path(__file__).parent / "e3_host/q2_fixture_check.py"
spec = importlib.util.spec_from_file_location("_q2_fixture_check_tests", PATH)
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)

if sys.platform.startswith("linux"):
    from local_hand_jobs import budget, quota_lifecycle, quota_grant as g
    from test_e3_quota_q2_supervisor import fixture, s, launcher
    from test_e3_quota_q2_chain import declaration_chain
    from q2_fixtures import BOOT, SECOND


class EntryTests(unittest.TestCase):
    def test_default_actual_isolated_entry_blocks_without_host_access(self):
        run = subprocess.run([sys.executable, "-I", "-B", str(PATH)], capture_output=True, timeout=10)
        self.assertEqual(3, run.returncode); self.assertEqual(b"", run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual("EXPLICIT_PRIVATE_FIXTURE_REQUIRED", result["reason"])
        self.assertFalse(result["q3_accepted"]); self.assertFalse(result["production_supported"])
        self.assertEqual("NOT_OBSERVED", result["quota_state"])
        self.assertEqual("NOT_RUN", result["execution_state"])

    def test_nonlinux_block_precedes_linux_file_constants(self):
        with mock.patch.object(c.sys, "platform", "win32"), mock.patch.object(c, "bootstrap", side_effect=AssertionError("source")):
            result = c.check(b"{}", "0" * 64, PATH.parents[2])
        self.assertEqual([dict(check="linux", status="BLOCKED", reason="LINUX_REQUIRED")], result["checks"])

    def test_report_keeps_independent_errors_and_blocks_dependents(self):
        report = c.Report()
        report.probe("one", lambda: (_ for _ in ()).throw(ValueError("FIRST_FAILURE")))
        report.probe("two", lambda: (_ for _ in ()).throw(OSError("private/path")))
        report.probe("three", lambda: self.fail("dependent call"), needs=("one",))
        report.probe("four", lambda: 5)
        self.assertEqual(["FIRST_FAILURE", "OSError", "PREREQUISITE_UNPROVEN"], [r["reason"] for r in report.rows[:3]])
        self.assertEqual("PASS", report.rows[-1]["status"])
        self.assertEqual("BLOCKED", report.result()["status"])
        self.assertNotIn("private/path", json.dumps(report.result()))

    def test_checked_report_never_grants_future_or_exit_authority(self):
        report = c.Report(); report.probe("snapshot", lambda: None)
        result = report.result()
        self.assertEqual("CHECKED", result["status"])
        self.assertTrue(result["independent_supervisor_stop_required"])
        self.assertFalse(result["q2_accepted"])
        self.assertEqual("NOT_MEASURED", result["capacity_peak"])
        self.assertIn("quota_and_enforcement", result["future_admission_required"])

    def test_bad_hash_duplicate_key_and_oversized_input_never_execute_sources(self):
        for raw, digest in ((b"{}", "0" * 64), (b'{"x":1,"x":2}', None), (b" " * (c.LIMIT + 1), None)):
            with self.subTest(size=len(raw)), mock.patch.object(c, "protected", side_effect=AssertionError("source read")), self.assertRaises(ValueError):
                c.bootstrap(raw, digest or c.sha(raw), PATH.parents[2])

    def test_deadline_guard_prevents_each_later_probe_without_refresh(self):
        report = c.Report()
        report.guard = lambda: (_ for _ in ()).throw(ValueError("FIXTURE_ORIGINAL_DEADLINE"))
        action = mock.Mock()
        report.probe("first", action); report.probe("second", action)
        action.assert_not_called()
        self.assertEqual(["FIXTURE_ORIGINAL_DEADLINE"] * 2, [row["reason"] for row in report.rows])


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux no-follow descriptors")
class LocalReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    @staticmethod
    def modeled_open(path, *, owner=0, directory=False, **kwargs):
        # Model protected ancestry only; real fd, no-follow/nonblock and content.
        return os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
                       | (os.O_DIRECTORY if directory else 0))

    def test_read_limit_and_changed_identity_reject(self):
        path = self.root / "record"; path.write_bytes(b"abc")
        with mock.patch.object(c, "opened", self.modeled_open):
            self.assertEqual(b"abc", c.protected(str(path), 3))
            with self.assertRaises(ValueError): c.protected(str(path), 2)
        fd = os.open(path, os.O_RDONLY)
        self.addCleanup(os.close, fd)
        before = os.fstat(fd)
        after = SimpleNamespace(**{name: getattr(before, name) for name in
            ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")})
        after.st_ino += 1
        with mock.patch.object(c.os, "fstat", side_effect=[before, after]), self.assertRaisesRegex(ValueError, "FIXTURE_FILE_CHANGED"):
            c.read_fd(fd, 3)

    def test_fifo_and_symlink_never_block_or_supply_regular_content(self):
        fifo = self.root / "fifo"; os.mkfifo(fifo)
        target = self.root / "plain"; target.write_bytes(b"plain")
        link = self.root / "link"; link.symlink_to(target)
        with mock.patch.object(c, "opened", self.modeled_open):
            with self.assertRaises(ValueError): c.protected(str(fifo), 100)
            with self.assertRaises(OSError): c.protected(str(link), 100)

    def test_real_opened_rejects_noncanonical_and_world_writable_ancestry(self):
        for path in ("relative", "//tmp/a", "/tmp/../etc/passwd", "/tmp/a/", "/"):
            with self.subTest(path=path), self.assertRaises(ValueError): c.opened(path)
        target = self.root / "read"; target.write_bytes(b"value")
        with self.assertRaisesRegex(ValueError, "FIXTURE_PROTECTION"):
            c.opened(str(target), owner=os.getuid())

    def test_directory_consumed_wrong_identity_and_gid_are_separate_failures(self):
        root = self.root / "empty"; root.mkdir(mode=0o700)
        info = root.stat(); pin = dict(path=str(root), device=info.st_dev, inode=info.st_ino)
        with mock.patch.object(c, "opened", self.modeled_open):
            c.directory(pin, owner=os.getuid(), gid=os.getgid())
            with self.assertRaisesRegex(ValueError, "FIXTURE_DIRECTORY_GROUP"): c.directory(pin, owner=os.getuid(), gid=os.getgid()+1)
            with self.assertRaisesRegex(ValueError, "FIXTURE_DIRECTORY_IDENTITY"): c.directory(dict(pin, inode=pin["inode"]+1), owner=os.getuid())
            (root / "retained").write_bytes(b"failure")
            with self.assertRaisesRegex(ValueError, "FIXTURE_DIRECTORY_CONSUMED"): c.directory(pin, owner=os.getuid())
            self.assertEqual(b"failure", (root / "retained").read_bytes())

    def test_absent_endpoint_does_not_unlink_existing_file_or_dangling_symlink(self):
        endpoint = self.root / "endpoint"
        with mock.patch.object(c, "opened", self.modeled_open):
            c.absent_endpoint(str(endpoint))
            endpoint.symlink_to(self.root / "missing")
            with self.assertRaisesRegex(ValueError, "FIXTURE_ENDPOINT_CONSUMED"): c.absent_endpoint(str(endpoint))
            self.assertTrue(endpoint.is_symlink())

    def test_executable_must_match_elf_digest_and_mode(self):
        path = self.root / "program"; path.write_bytes(b"\x7fELFmodel"); path.chmod(0o755)
        pin = dict(path=str(path), sha256=c.sha(path.read_bytes()))
        with mock.patch.object(c, "opened", self.modeled_open):
            c.executable(pin)
            with self.assertRaises(ValueError): c.executable(dict(pin, sha256="0"*64))
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "FIXTURE_EXECUTABLE_MODE"): c.executable(pin)

    def make_ledger(self):
        path = self.root / "jobs.sqlite"
        db = sqlite3.connect(path)
        db.executescript("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);"
                        "INSERT INTO metadata VALUES('schema','1'),('authority_id','fixture'),('ledger_id','model');"
                        "CREATE TABLE operations(id INTEGER); CREATE TABLE events(id INTEGER); CREATE TABLE leases(id INTEGER);"
                        "CREATE TABLE counters(key TEXT,value INTEGER); INSERT INTO counters VALUES('generation',1);")
        db.commit(); db.close(); path.chmod(0o600); self.root.chmod(0o700)
        return path, SimpleNamespace(broker_root=str(self.root), authority_id="fixture", generation=2)

    def test_existing_empty_ledger_is_read_in_ram_without_host_sqlite_or_writes(self):
        path, policy = self.make_ledger(); before = path.read_bytes(); entries = sorted(self.root.iterdir())
        connect = sqlite3.connect
        def memory_only(name, *args, **kwargs):
            self.assertEqual(":memory:", name)
            return connect(name, *args, **kwargs)
        with mock.patch.object(c, "opened", self.modeled_open), mock.patch.object(c.sqlite3, "connect", memory_only):
            c.empty_ledger(policy, os.getuid(), [2, 1])
        self.assertEqual(before, path.read_bytes()); self.assertEqual(entries, sorted(self.root.iterdir()))

    def test_used_ledger_and_generation_drift_cannot_be_recycled(self):
        path, policy = self.make_ledger()
        with mock.patch.object(c, "opened", self.modeled_open):
            with self.assertRaisesRegex(ValueError, "FIXTURE_LEDGER_GENERATION"): c.empty_ledger(policy, os.getuid(), [2, 2])
            db = sqlite3.connect(path); db.execute("INSERT INTO events VALUES(1)"); db.commit(); db.close()
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "FIXTURE_LEDGER_CONSUMED"): c.empty_ledger(policy, os.getuid(), [2, 1])
        self.assertEqual(before, path.read_bytes())

    def test_wal_shm_or_rollback_sidecar_prevents_false_empty_snapshot(self):
        path, policy = self.make_ledger()
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(str(path) + suffix); sidecar.write_bytes(b"retained")
            with self.subTest(suffix=suffix), mock.patch.object(c, "opened", self.modeled_open), \
                 mock.patch.object(c.sqlite3, "connect", side_effect=AssertionError("must not ignore sidecar")), \
                 self.assertRaisesRegex(ValueError, "FIXTURE_LEDGER_SIDECAR_REQUIRES_ORDINARY_ADMISSION"):
                c.empty_ledger(policy, os.getuid(), [2, 1])
            self.assertEqual(b"retained", sidecar.read_bytes()); sidecar.unlink()

    def test_closed_wal_header_is_changed_only_on_memory_snapshot(self):
        path, policy = self.make_ledger()
        db = sqlite3.connect(path); db.execute("PRAGMA journal_mode=WAL"); db.close()
        before = path.read_bytes(); self.assertEqual(b"\2\2", before[18:20])
        with mock.patch.object(c, "opened", self.modeled_open): c.empty_ledger(policy, os.getuid(), [2, 1])
        self.assertEqual(before, path.read_bytes())

    def test_views_cannot_replace_required_tables(self):
        path, policy = self.make_ledger()
        db = sqlite3.connect(path); db.executescript("DROP TABLE events; CREATE VIEW events AS SELECT 1 AS id WHERE 0;"); db.close()
        with mock.patch.object(c, "opened", self.modeled_open), self.assertRaisesRegex(ValueError, "FIXTURE_LEDGER_SCHEMA"):
            c.empty_ledger(policy, os.getuid(), [2, 1])

    def installed_fixture(self):
        from local_hand import provenance
        installed = self.root / "wheel"; files = {}
        for package in c.PACKAGES:
            folder = installed / package; folder.mkdir(parents=True)
            path = folder / "__init__.py"; path.write_bytes(b"# modeled installed source\n")
            files[package + "/__init__.py"] = c.sha(path.read_bytes())
        worker = installed / "local_hand/worker.py"
        worker.write_text('VALUE = "source"\n')
        files["local_hand/worker.py"] = c.sha(worker.read_bytes())
        digest = c.sha(json.dumps(dict(schema_version="infra-local-hand-full-payload/v1", files=files),
                                 sort_keys=True, separators=(",", ":")).encode())
        metadata = dict(schema_version=provenance.BUILD_SCHEMA, product_version=provenance.VERSION,
                        source_commit="a"*40, artifact_kind="wheel", files=files)
        (installed / "local_hand" / provenance.METADATA_NAME).write_text(json.dumps(metadata))
        nested = dict(resident=dict(installation=dict(package_root=str(installed), source_commit="a"*40, payload_digest=digest, files=files)))
        return installed, nested, digest

    def test_installed_full_payload_checks_actual_bytes_metadata_and_extra_entries(self):
        installed, nested, digest = self.installed_fixture()
        with mock.patch.object(c, "opened", self.modeled_open):
            self.assertEqual(digest, c.installed_release(nested))
            (installed / "local_hand_jobs/plugin.so").write_bytes(b"opaque")
            with self.assertRaisesRegex(ValueError, "FIXTURE_INSTALLED_EXTRA_FILE"): c.installed_release(nested)

    def test_pip_style_current_interpreter_caches_match_resident_contract(self):
        from local_hand import provenance
        installed, nested, digest = self.installed_fixture()
        source = installed / "local_hand/worker.py"
        for optimize in (0, 1, 2):
            py_compile.compile(str(source), optimize=optimize, doraise=True)
        before = {path: path.read_bytes() for path in installed.rglob("*.pyc")}
        self.assertEqual(digest, provenance.full_payload_digest(installed))
        with mock.patch.object(c, "opened", self.modeled_open):
            self.assertEqual(digest, c.installed_release(nested))
        self.assertEqual(before, {path: path.read_bytes() for path in installed.rglob("*.pyc")})

    def test_timestamp_valid_poisoned_cache_is_not_loaded_or_admitted(self):
        installed, nested, _ = self.installed_fixture()
        source = installed / "local_hand/worker.py"
        cache = Path(py_compile.compile(str(source), doraise=True))
        original = cache.read_bytes()
        poisoned = marshal.dumps(compile('VALUE = "poison"\n', str(source), "exec", dont_inherit=True))
        self.assertEqual(len(original[16:]), len(poisoned))
        cache.write_bytes(original[:16] + poisoned)
        # The normal interpreter accepts this cache: the header still matches
        # the untouched .py. The checker must compare executable content.
        result = subprocess.run([sys.executable, "-I", "-B", "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); from local_hand import worker; print(worker.VALUE)",
            str(installed)], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("poison", result.stdout.strip())
        with mock.patch.object(c, "opened", self.modeled_open), mock.patch.object(marshal, "loads", side_effect=AssertionError("unmarshal")), \
             self.assertRaisesRegex(ValueError, "FIXTURE_WHEEL_CACHE_BYTES"):
            c.installed_release(nested)
        self.assertEqual(original[:16] + poisoned, cache.read_bytes())

    def test_cache_symlinks_foreign_interpreter_and_extra_source_are_rejected(self):
        installed, nested, _ = self.installed_fixture()
        source = installed / "local_hand/worker.py"
        cache = Path(py_compile.compile(str(source), doraise=True))
        original = cache.read_bytes(); cache.unlink()
        cache.symlink_to(source)
        with mock.patch.object(c, "opened", self.modeled_open), self.assertRaises(OSError):
            c.installed_release(nested)
        cache.unlink()
        for name, reason in (("worker.foreign-999.pyc", "FIXTURE_WHEEL_CACHE_NAME"),
                             ("extra." + sys.implementation.cache_tag + ".pyc", "FIXTURE_WHEEL_CACHE_SOURCE")):
            extra = cache.with_name(name); extra.write_bytes(original)
            with mock.patch.object(c, "opened", self.modeled_open), self.assertRaisesRegex(ValueError, reason):
                c.installed_release(nested)
            extra.unlink()

    def test_root_private_ancestor_cannot_pass_as_ordinary_readable_declaration(self):
        private = self.root / "private"; private.mkdir(mode=0o700)
        declarations = private / "declarations"; declarations.mkdir(mode=0o755)
        private_id = (private.stat().st_dev, private.stat().st_ino)
        real_fstat = os.fstat
        def protected_owner(fd):
            # Actual directory modes and descriptors. Model root ownership and
            # secure external ancestors because CI cannot chown or drop UID.
            info = real_fstat(fd)
            values = {name: getattr(info, name) for name in
                      ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")}
            values.update(st_uid=0, st_gid=0)
            if stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) != private_id:
                values["st_mode"] = stat.S_IFDIR | 0o755
            return SimpleNamespace(**values)
        with mock.patch.object(c.os, "fstat", protected_owner):
            fd = c.opened(str(declarations), directory=True); os.close(fd)
            with self.assertRaisesRegex(ValueError, "FIXTURE_ORDINARY_PATH_ACCESS"):
                c.opened(str(declarations), directory=True, reader=(12345, 12345))
            private.chmod(0o711)
            with self.assertRaisesRegex(ValueError, "FIXTURE_ORDINARY_PATH_ACCESS"):
                c.opened(str(declarations), directory=True, reader=(12345, 12345))
            fd = c.opened(str(declarations), directory=True, reader=(12345, 12345), ancestor_bits=1)
            os.close(fd)
            private.chmod(0o755)
            fd = c.opened(str(declarations), directory=True, reader=(12345, 12345)); os.close(fd)

    def test_ordinary_acl_and_unreadable_leaf_remain_unproven(self):
        path = self.root / "file"; path.write_bytes(b"read only"); path.chmod(0o600)
        fd = os.open(path, os.O_RDONLY); self.addCleanup(os.close, fd)
        reader = (os.getuid() + 10000, os.getgid() + 10000)
        with self.assertRaisesRegex(ValueError, "FIXTURE_ORDINARY_PATH_ACCESS"):
            c.ordinary_access(fd, reader, 4)
        path.chmod(0o644)
        c.ordinary_access(fd, reader, 4)
        with mock.patch.object(c.os, "getxattr", return_value=b"mode bits are insufficient"), \
             self.assertRaisesRegex(ValueError, "FIXTURE_ORDINARY_ACL_UNPROVEN"):
            c.ordinary_access(fd, reader, 4)
        seen = []
        def default_acl(fd, name):
            seen.append(name)
            if name.endswith("_default"): return b"inherited access"
            raise OSError(errno.ENODATA, "absent")
        with mock.patch.object(c.os, "getxattr", side_effect=default_acl), \
             self.assertRaisesRegex(ValueError, "FIXTURE_ORDINARY_ACL_UNPROVEN"):
            c.ordinary_access(fd, reader, 4, default_acl=True)
        self.assertEqual(["system.posix_acl_access", "system.posix_acl_default"], seen)


@unittest.skipUnless(sys.platform.startswith("linux"), "Modeled Linux host authority")
class AggregateTests(unittest.TestCase):
    def setUp(self):
        self.value = fixture(); chain, _ = declaration_chain()
        cap = chain["installation"]["capacity"]; cap["management"]["cpu_ns"] = 500*SECOND
        for phase in chain["phases"].values(): phase["grant"]["management"]["capacity_digest"] = g.digest(cap)
        self.value["launcher"].update(schema=launcher.CHAIN_SCHEMA, purpose="ISOLATED_Q2_CHAIN", assembly=chain)
        self.value["launcher"]["resident"]["ordinary"].update(uid=1000, gid=1000, initial_userns=dict(device=4, inode=5))
        self.clock = dict(boot_id=BOOT, boottime_ns=2*SECOND)
        self.binding = s.validate(self.value, launcher, self.clock)
        self.templates = s.templates(self.value["launcher"])

    def invoke(self, *, failures=(), own=True):
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(c, "bootstrap", return_value=(self.value, s, launcher)))
            stack.enter_context(mock.patch.object(c, "fixed", return_value=b"systemd\n"))
            for name in ("getuid", "geteuid", "getgid", "getegid"):
                stack.enter_context(mock.patch.object(c.os, name, return_value=0))
            stack.enter_context(mock.patch.object(budget, "current_clock", return_value=self.clock))
            stack.enter_context(mock.patch.object(c, "static_binding", return_value=self.templates))
            for name in ("namespace", "installed_release", "policy_snapshot", "resident_paths", "empty_ledger", "executable", "absent_endpoint",
                         "directory", "storage_geometry", "manager_delegation"):
                stack.enter_context(mock.patch.object(c, name, side_effect=ValueError(name.upper()+"_FAILED") if name in failures else None))
            stack.enter_context(mock.patch.object(quota_lifecycle, "parent", return_value=({}, True)))
            stack.enter_context(mock.patch.object(s, "admit", return_value={} if own else None,
                                                  side_effect=None if own else ValueError("OWN_IDENTITY_UNPROVEN")))
            controls = mock.Mock()
            controls.show.return_value = dict(Id=self.binding["target"].unit, LoadState="not-found", Job="")
            stack.enter_context(mock.patch.object(s, "Controls", return_value=controls))
            for name in ("supervise", "controller_role"):
                stack.enter_context(mock.patch.object(s, name, side_effect=AssertionError("target mutation")))
            stack.enter_context(mock.patch.object(launcher, "save", side_effect=AssertionError("write")))
            result = c.check(b"model", "a"*64, PATH.parents[2])
        return result, controls

    def test_one_batch_checks_all_three_stage_dirs_roots_and_endpoints_without_launch(self):
        result, controls = self.invoke()
        self.assertEqual("CHECKED", result["status"], result)
        names = {row["check"] for row in result["checks"]}
        for phase in c.PHASES:
            self.assertTrue({phase+"_endpoint", phase+"_control", phase+"_output", phase+"_root_work"} <= names)
        self.assertIn("original_empty_ledger", names); self.assertIn("supervisor_storage_geometry", names)
        self.assertIn("ordinary_resident_path_access", names)
        controls.call.assert_not_called()
        controls.show.assert_called_once()
        self.assertFalse(result["q3_accepted"])

    def test_multiple_independent_host_defects_appear_in_one_report(self):
        result, _ = self.invoke(failures=("namespace", "directory", "executable", "absent_endpoint"))
        reasons = {row.get("reason") for row in result["checks"]}
        self.assertTrue({"NAMESPACE_FAILED", "DIRECTORY_FAILED", "EXECUTABLE_FAILED", "ABSENT_ENDPOINT_FAILED"} <= reasons)
        self.assertEqual("BLOCKED", result["status"])

    def test_missing_own_service_blocks_manager_queries_without_faking_external_supervision(self):
        result, controls = self.invoke(own=False)
        rows = {row["check"]: row for row in result["checks"]}
        self.assertEqual("OWN_IDENTITY_UNPROVEN", rows["original_supervisor"]["reason"])
        self.assertEqual("PREREQUISITE_UNPROVEN", rows["target_not_started"]["reason"])
        controls.show.assert_not_called(); controls.call.assert_not_called()
        self.assertTrue(result["independent_supervisor_stop_required"])

    def test_source_auth_failure_still_reports_independent_pid1_and_uid_checks(self):
        with mock.patch.object(c, "bootstrap", side_effect=ValueError("SOURCE_CHANGED")), \
             mock.patch.object(c, "fixed", return_value=b"other\n"), \
             mock.patch.object(c.os, "getuid", return_value=1234):
            result = c.check(b"x", "a"*64, PATH.parents[2])
        reasons = {row.get("reason") for row in result["checks"]}
        self.assertTrue({"SOURCE_CHANGED", "SYSTEMD_REQUIRED", "ADMINISTRATOR_REQUIRED", "PREREQUISITE_UNPROVEN"} <= reasons)


if __name__ == "__main__":
    unittest.main()
