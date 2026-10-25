"""Offline migration: actual files, SQLite, inherited locks and crash recovery.

Systemd observations use a fixed in-memory bus fixture; no host service is
stopped, masked or started. The production observer and complete-config verifier
remain exercised. The separate payload-release check has its existing tests.
"""
import copy
import fcntl
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
import io
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from admin.local_hand_deploy import bootstrap, files
from admin.local_hand_deploy import cli
from admin.local_hand_deploy.model import DeployError, operation_id
from admin.local_hand_deploy.planner import PROFILE_SCHEMA
from admin.local_hand_deploy.runtime import PlanningEnvironment
from admin.local_hand_deploy.store import Store
from local_hand_jobs import maintenance, startup


class Bus:
    def __init__(self, units):
        self.units, self.pending = units, []
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def unit(self, name):
        return self.units.get(name, {"LoadState": "not-found", "ActiveState": "inactive", "MainPID": 0, "Job": [0, "/"]})
    def jobs(self): return self.pending


class Observer(bootstrap.OfflineObserver):
    def verify_target(self, target, candidates=None):
        self.environment._verify_components(target["selection"], candidates)

    def retention(self, target, entries, candidates=None):
        # These fixtures model legacy closure/file publication, not a complete
        # installed task reader. Production reader bytes have separate tests.
        return {"preparations": {}, "results": {"tasks": []}}


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.uid = os.geteuid()
        self.records = self.root / "records"
        self.records.mkdir(mode=0o700)
        self.lock = self.records / "service.lock"
        self.lock.write_bytes(b""); self.lock.chmod(0o600)
        self.legacy_config = self.root / "old-manager.json"
        self.config, self.candidate = self.root / "manager.json", self.root / "candidate.json"
        self.descriptor = self.root / "selection.json"
        self.gate_dir = self.root / "gate"
        self.gate_dir.mkdir(mode=0o700)
        old = {"schema": "local-hand-resident-service/v1", "private_root": str(self.records),
               "socket": str(self.root / "manager.sock"), "uid": self.uid,
               "installation": {"installed": {"payload_digest": "c" * 64}}}
        self.old = copy.deepcopy(old)
        candidate = {**old, "maintenance": {"schema": maintenance.CONFIG_SCHEMA, "node_id": "node",
            "deployment_digest": "a" * 64, "directory": str(self.gate_dir), "startup_descriptor": str(self.descriptor)}}
        self.write(self.legacy_config, old); self.write(self.candidate, candidate)
        self.profile = {"schema": PROFILE_SCHEMA, "owner_uid": self.uid,
            "startup_descriptor": str(self.descriptor), "maintenance_directory": str(self.gate_dir),
            "filesystem_support": {"ordinary_handles": True, "fsid": True, "reboot_verified": True},
            "guarded_components": {"manager": {"configuration": str(self.config), "entrypoints": ["prepare", "execute", "cli", "listener"]}},
            "probes": {"manager": {"kind": "resident", "socket": str(self.root / "manager.sock"), "peer_uid": self.uid}},
            "systemd": {"units": {"guarded.service": {"component": "manager"}}}}
        self.target = {"deployment_digest": "a" * 64, "services": {"guarded.service": {"running": False, "policy": "disabled"}},
            "selection": {"schema": startup.SCHEMA, "node_id": "node", "deployment_digest": "a" * 64,
                "decision_id": "placeholder", "mode": "stable", "owner": None, "permit": None,
                "members": [{"path": str(self.config), "sha256": hashlib.sha256(startup.canonical(candidate)).hexdigest()}],
                "components": {"manager": {"configuration_digest": maintenance.digest(old), "payload_digest": "c" * 64,
                                           "entry": "local", "running": False}}}}
        stopped = {"ActiveState": "inactive", "MainPID": 0, "ControlPID": 0, "Job": [0, "/"], "ControlGroup": ""}
        self.bus = Bus({"old.service": {**stopped, "LoadState": "masked", "UnitFileState": "masked"},
            "guarded.service": {**stopped, "LoadState": "loaded", "UnitFileState": "disabled", "NeedDaemonReload": False,
                "ExecStart": [[sys.executable, [sys.executable, "-B", "-m", "admin.local_hand_system_manager.resident_service",
                                               "--config", str(self.config)], False]],
                "Environment": ["PYTHONPATH=" + str(Path(bootstrap.__file__).parents[2])]}})
        self.observer = Observer(self.profile, bus_factory=lambda: self.bus)
        self.manifest = {"schema": bootstrap.MANIFEST_SCHEMA, "request_id": "migration", "node_id": "node",
            "legacy": [{"kind": "resident", "unit": "old.service", "configuration": str(self.legacy_config)}],
            "files": [{"target": str(self.config), "source": str(self.candidate)}], "target": self.target, "profile": self.profile}
        try:
            with open(self.lock, "rb") as source: files._binding(source.fileno())
        except files.FileError as error:
            if error.code == "UNSUPPORTED": self.skipTest(str(error))
            raise
        self.store = Store(self.root / "state", "node", owner_uid=self.uid)
        self.store.initialize()

    def write(self, path, value):
        path.write_bytes(startup.canonical(value)); path.chmod(0o600)

    def plan(self): return bootstrap.build_bootstrap_plan(self.manifest, self.observer)
    def adopt(self, plan): return bootstrap.adopt_bootstrap(self.store, plan, observer=self.observer)

    def test_result_readback_failure_retains_partial_import_and_resumes_same_files(self):
        plan = self.plan()
        original = self.observer.retention
        def fail_after_publication(target, entries, candidates=None):
            if candidates is None:
                raise bootstrap.DeployError("BOOTSTRAP_RETENTION", "synthetic result route interruption")
            return original(target, entries, candidates)
        with patch.object(self.observer, "retention", side_effect=fail_after_publication):
            failed = self.adopt(plan)
        self.assertFalse(failed["released"])
        self.assertIsNone(failed["decision"])
        identity = self.config.stat().st_ino
        self.assertFalse((self.gate_dir / "state.json").exists())
        recovered = self.adopt(plan)
        self.assertTrue(recovered["released"])
        self.assertEqual(identity, self.config.stat().st_ino)

    def test_original_result_drift_refuses_before_any_imported_configuration(self):
        plan = self.plan()
        with patch.object(self.observer, "retention", return_value={"changed": True}):
            failed = self.adopt(plan)
        self.assertFalse(failed["released"])
        self.assertFalse(self.config.exists())
        self.assertTrue(self.adopt(plan)["released"])

    def test_legacy_mcp_retained_routes_are_bound_beyond_current_manager_tasks(self):
        catalog = self.root / "old-catalog"; catalog.mkdir(mode=0o700)
        descriptor = self.root / "old-resident.json"
        self.write(descriptor, {"catalog": str(catalog), "retained": ["/protected/historical-policy"]})
        config = self.root / "old-mcp.json"
        self.write(config, {"schema": "gx10-single-owner-mcp/v1", "anchor_policy": "/protected/anchor-policy",
                            "resident": str(descriptor)})
        self.manifest['legacy'].append({'kind': 'mcp', 'unit': 'old-mcp.service', 'configuration': str(config)})
        entries = bootstrap._legacy(self.manifest['legacy'], self.uid)
        self.assertEqual(['/protected/anchor-policy', '/protected/historical-policy'], entries[-1]['read_policies'])
        self.write(descriptor, {"catalog": str(catalog), "retained": []})
        with self.assertRaisesRegex(DeployError, 'historical MCP read bindings changed'):
            self.observer.observe(entries, self.target)

    def test_bootstrap_cannot_hide_a_historical_ledger_outside_preparation_catalog(self):
        from types import SimpleNamespace
        from admin.local_hand_deploy import preparations, retained_reader
        empty = {'schema': 'local-hand-retained-readback/v1', 'tasks': [], 'bytes_verified': 0}
        prior = {'schema': empty['schema'], 'tasks': [{'operation_id': 'original-history', 'artifacts': []}], 'bytes_verified': 0}
        profile = {'owner_uid': self.uid, 'probes': {'mcp': {'kind': 'mcp'}}}
        observer = bootstrap.OfflineObserver(profile)
        observer.environment = SimpleNamespace(preparation_inventory=lambda _: {'tasks': []},
                                                retained_results=lambda *_: empty)
        with patch.object(preparations, 'inventory', return_value={'tasks': []}), \
                patch.object(retained_reader, 'offline_readback', return_value=prior), \
                self.assertRaisesRegex(DeployError, 'omit an original historical read route'):
            observer.retention(self.target, [{'kind': 'mcp', 'read_policies': ['/protected/old-policy']}])

    def record(self, *, launch=False, closed=True):
        operation = "00000000-0000-4000-8000-000000000001"
        directory = self.records / operation; directory.mkdir(mode=0o700)
        attempt = directory / "attempt-1"; attempt.mkdir(mode=0o700)
        output = attempt / "execution"; output.mkdir(mode=0o700)
        self.write(attempt / "preparation-delivery.json", {"command": ["systemd-run", "--unit=prepare.service"]})
        self.write(attempt / "preparation-exit.json", {"returncode": 0})
        value = {"operation_id": operation, "attempt": str(attempt), "prepare_unit": "prepare.service",
                 "controller_unit": "controller.service", "output": str(output), "boot_id": startup.boot_id(), "state": "READY"}
        launch_path = attempt / "launch-static.json"
        parent = {"path": "/lhbootstrapfixture.slice"}
        launch_spec = {"controller_envelope": {"controller": {"unit": "controller.service"}},
            "policy": {"process_manager": {"cgroup": "/sys/fs/cgroup/lhbootstrapfixture.slice"}},
            "chain": {"phases": {phase: {"grant": {"query_parent": parent, "management_parent": parent},
                "service": {"parent": parent}, "peer": {"parent": parent}} for phase in ("preflight", "business", "evidence")}}}
        self.write(launch_path, launch_spec)
        value["launch_path"] = str(launch_path)
        self.write(directory / "current.json", value)
        if launch:
            self.write(output / "launch-intent.json", {"started": "retained"})
            if closed: self.write(output / "finished.json", {"returncode": 0, "streams_eof": True})
        return directory, attempt, output

    def prepared(self, old_boot):
        output = self.root / "prepared-output"; output.mkdir(mode=0o700)
        lock = output / "service.lock"; lock.write_bytes(b""); lock.chmod(0o600)
        launch_path = self.root / "prepared-launch.json"
        parent = {"path": "/lhbootstrapfixture.slice"}
        launch = {"controller_envelope": {"controller": {"unit": "prepared-controller.service", "boot_id": old_boot}},
            "policy": {"process_manager": {"cgroup": "/sys/fs/cgroup/lhbootstrapfixture.slice"}},
            "chain": {"phases": {phase: {"grant": {"query_parent": parent, "management_parent": parent},
                "service": {"parent": parent}, "peer": {"parent": parent}} for phase in ("preflight", "business", "evidence")}}}
        self.write(launch_path, launch)
        self.write(output / "launch-intent.json", {"started": "retained"})
        config = self.root / "old-prepared.json"
        self.write(config, {"schema": "local-hand-prepared-service/v1", "output": str(output),
            "launch_path": str(launch_path), "launch_sha256": hashlib.sha256(launch_path.read_bytes()).hexdigest(),
            "socket": str(self.root / "prepared.sock")})
        self.manifest["legacy"].append({"kind": "prepared", "unit": "old-prepared.service", "configuration": str(config)})
        self.bus.units["old-prepared.service"] = copy.deepcopy(self.bus.units["old.service"])
        return output, launch_path

    def test_plan_read_only_and_import_stopped_guarded_baseline(self):
        before = {str(path): (path.lstat().st_ino, path.lstat().st_mtime_ns) for path in self.root.rglob("*")}
        plan = self.plan()
        self.assertEqual(before, {str(path): (path.lstat().st_ino, path.lstat().st_mtime_ns) for path in self.root.rglob("*")})
        operation = self.adopt(plan)
        self.assertTrue(operation["released"])
        self.assertEqual("COMMITTED", operation["decision"])
        self.assertEqual(False, startup.read_selection(self.descriptor, owner_uid=self.uid)["components"]["manager"]["running"])
        gate = maintenance.MaintenanceGate(self.gate_dir, "node", owner_uid=self.uid)
        self.assertEqual("OPEN", gate.snapshot()["state"])
        self.assertEqual(operation["id"], self.adopt(plan)["id"])
        with self.assertRaises(DeployError): bootstrap.rollback_bootstrap(self.store, operation["id"], observer=self.observer)

    def test_active_original_lock_is_not_replaced_or_treated_offline(self):
        # A second process owns the actual legacy service lock.
        ready_r, ready_w = os.pipe(); release_r, release_w = os.pipe()
        child = os.fork()
        if child == 0:
            os.close(ready_r); os.close(release_w)
            fd = os.open(self.lock, os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX)
            os.write(ready_w, b"1"); os.read(release_r, 1); os._exit(0)
        os.close(ready_w); os.close(release_r)
        try:
            self.assertEqual(b"1", os.read(ready_r, 1))
            with self.assertRaisesRegex(DeployError, "still alive"): self.plan()
        finally:
            os.write(release_w, b"1"); os.close(release_w); os.close(ready_r); os.waitpid(child, 0)

    def test_missing_lock_is_not_created(self):
        self.lock.unlink()
        with self.assertRaises(FileNotFoundError): self.plan()
        self.assertFalse(self.lock.exists())

    def test_persistent_mask_and_no_job_are_real_preconditions(self):
        self.bus.units["old.service"]["UnitFileState"] = "masked-runtime"
        with self.assertRaises(DeployError): self.plan()
        self.bus.units["old.service"]["UnitFileState"] = "masked"
        self.bus.pending = [[1, "old.service", "start", "waiting", "/job", "/unit"]]
        with self.assertRaises(DeployError): self.plan()

    def test_direct_cli_session_needs_original_controller_closed(self):
        self.record(launch=True)
        self.bus.units["controller.service"] = {"LoadState": "loaded", "ActiveState": "active", "MainPID": 123, "Job": [0, "/"]}
        with self.assertRaises(DeployError): self.plan()

    def test_ready_and_old_failure_records_do_not_replay_or_require_business_success(self):
        _, attempt, output = self.record(launch=True)
        self.write(output / "finished.json", {"returncode": 7, "streams_eof": True})
        before = {str(path): path.read_bytes() for path in self.records.rglob("*.json")}
        operation = self.adopt(self.plan())
        self.assertTrue(operation["released"])
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.records.rglob("*.json")})

    def test_missing_same_boot_delivery_closure_refuses_before_mutation(self):
        self.record(launch=True, closed=False)
        with self.assertRaises(RuntimeError): self.plan()
        self.assertEqual(self.old, bootstrap._read(self.legacy_config, self.uid))
        self.assertFalse(self.config.exists())
        self.assertFalse(self.descriptor.exists())

    def test_wrong_guarded_unit_configuration_or_import_tree_rejected(self):
        self.bus.units["guarded.service"]["Environment"] = ["PYTHONPATH=/other/legacy/tree"]
        with self.assertRaises(DeployError): self.plan()

    def test_existing_unguarded_configuration_cannot_be_import_rollback_baseline(self):
        self.write(self.config, self.old)
        with self.assertRaisesRegex(DeployError, "initially absent"): self.plan()

    def test_import_cannot_rewrite_its_old_dispatch_configuration(self):
        self.manifest["files"].append({"source": str(self.candidate), "target": str(self.legacy_config)})
        self.target["selection"]["members"].append({"path": str(self.legacy_config),
            "sha256": hashlib.sha256(self.candidate.read_bytes()).hexdigest()})
        with self.assertRaisesRegex(DeployError, "overwrite old"): self.plan()

    def test_queued_business_stage_prevents_import_after_controller_exit(self):
        self.record(launch=True)
        self.bus.units["stage.service"] = {"Slice": "lhbootstrapfixture.slice", "ActiveState": "inactive", "LoadState": "loaded"}
        self.bus.pending = [[1, "stage.service", "start", "waiting", "/job", "/unit"]]
        with self.assertRaisesRegex(DeployError, "task stage"): self.plan()

    def test_host_reboot_closes_old_channel_without_fabricating_finished_record(self):
        directory, _, output = self.record(launch=True, closed=False)
        record = bootstrap._read(directory / "current.json", self.uid)
        record["boot_id"] = "00000000-0000-4000-8000-000000000099"
        self.write(directory / "current.json", record)
        operation = self.adopt(self.plan())
        self.assertTrue(operation["released"])
        self.assertFalse((output / "finished.json").exists())

    def test_prepared_reboot_closes_original_channel_without_finished_record(self):
        output, _ = self.prepared("00000000-0000-4000-8000-000000000099")
        operation = self.adopt(self.plan())
        self.assertTrue(operation["released"])
        self.assertFalse((output / "finished.json").exists())

    def test_prepared_same_boot_missing_closure_is_not_treated_as_reboot(self):
        self.prepared(startup.boot_id())
        with self.assertRaises(DeployError): self.plan()

    def test_import_cannot_rewrite_retained_prepared_launch(self):
        _, launch_path = self.prepared("00000000-0000-4000-8000-000000000099")
        self.manifest["files"].append({"source": str(self.candidate), "target": str(launch_path)})
        self.target["selection"]["members"].append({"path": str(launch_path),
            "sha256": hashlib.sha256(self.candidate.read_bytes()).hexdigest()})
        with self.assertRaisesRegex(DeployError, "overwrite old"): self.plan()

    def test_cli_bootstrap_and_resume_route_original_operation(self):
        plan = self.plan()
        path = self.root / "plan.json"; self.write(path, plan)
        output = io.StringIO()
        with patch.object(cli, "implementation_identity", return_value={"selected": "fixture"}), \
                patch.object(bootstrap, "OfflineObserver", return_value=self.observer), redirect_stdout(output), redirect_stderr(output):
            first = cli.main(["--state", str(self.store.root), "--node", "node", "bootstrap-adopt", str(path)])
            second = cli.main(["--state", str(self.store.root), "--node", "node", "resume", operation_id("migration")])
        self.assertEqual((0, 0), (first, second), output.getvalue())

    def test_child_crash_after_publish_resumes_same_object(self):
        plan = self.plan()
        child = os.fork()
        if child == 0:
            execute = files.execute_file
            def interrupted(action, **kwargs):
                execute(action, **kwargs); os._exit(23)
            with patch.object(files, "execute_file", interrupted): self.adopt(plan)
            os._exit(24)
        _, status = os.waitpid(child, 0)
        self.assertEqual(23, os.waitstatus_to_exitcode(status))
        original_inode = self.config.stat().st_ino
        operation = self.adopt(plan)
        self.assertTrue(operation["released"])
        self.assertEqual(original_inode, self.config.stat().st_ino)

    def test_lost_selection_response_resumes_exact_decision(self):
        plan = self.plan()
        publish = startup.publish
        def lost(*args, **kwargs):
            publish(*args, **kwargs)
            raise OSError("response lost")
        with patch.object(startup, "publish", lost): first = self.adopt(plan)
        self.assertEqual("COMMITTED", first["decision"])
        self.assertFalse(first["released"])
        before = self.descriptor.stat().st_ino
        final = self.adopt(plan)
        self.assertTrue(final["released"])
        self.assertEqual(first["decision_id"], final["decision_id"])
        self.assertEqual(before, self.descriptor.stat().st_ino)

    def test_partial_import_can_restore_files_without_opening_legacy(self):
        plan = self.plan()
        execute = files.execute_file
        def lost(action, **kwargs):
            execute(action, **kwargs)
            raise OSError("directory reply lost")
        with patch.object(files, "execute_file", lost): first = self.adopt(plan)
        self.assertFalse(first["released"])
        final = bootstrap.rollback_bootstrap(self.store, first["id"], observer=self.observer)
        self.assertEqual("ROLLED_BACK", final["decision"])
        self.assertEqual(self.old, bootstrap._read(self.legacy_config, self.uid))
        self.assertFalse(self.config.exists())
        self.assertFalse(self.descriptor.exists())
        self.assertFalse((self.gate_dir / "gate.json").exists())
        self.assertEqual("masked", self.bus.units["old.service"]["UnitFileState"])

    def test_retained_task_drift_refuses_without_overwriting(self):
        directory, _, _ = self.record()
        plan = self.plan()
        record = bootstrap._read(directory / "current.json", self.uid)
        self.write(directory / "current.json", {**record, "state": "INDEPENDENT_CHANGE"})
        operation = self.adopt(plan)
        self.assertFalse(operation["released"])
        self.assertEqual(self.old, bootstrap._read(self.legacy_config, self.uid))
        self.assertFalse(self.config.exists())
        self.assertEqual("BOOTSTRAP_CHANGED", operation["errors"]["primary"][-1]["code"])


if __name__ == "__main__": unittest.main()
