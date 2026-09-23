"""Real local files/ledger with explicitly simulated namespace/cgroup/quota facts.

These checks prove preparation and interruption semantics, not real systemd or
kernel project-quota enforcement. No NAS or deployment paths are used.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand_jobs import bootstrap, bootstrap_roots, budget, runner
from local_hand_jobs.contract import JobError
from local_hand_jobs.state import StateStore
from test_local_hand_jobs_runner import budgeted_plan


class BootstrapPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        state_root = self.root / "state"
        state_root.mkdir(mode=0o700)
        self.db = StateStore(state_root / "ledger.sqlite", "fixture-authority", "fixture-ledger", initialize=True)
        self.addCleanup(self.db.close)
        self.slot = {"slot_id": "preparation-fixture", "roots": {}}
        for name in ("work", "evidence", "temporary"):
            path = self.root / name
            path.mkdir(mode=0o700)
            info = path.stat()
            self.slot["roots"][name] = {"path": str(path), "device": info.st_dev,
                "inode": info.st_ino, "uid": info.st_uid}
        self.original = {name: str(self.root / "planned" / name) for name in self.slot["roots"]}
        self.execution = {"kind": "host.inspect", "operation_id": "fixture", "roots": self.original,
            "writable": list(self.original.values()), "readonly": [], "storage": {}, "stages": []}
        with self.db.transaction() as tx:
            self.row = self.db.insert(tx, "job", "fixture", "fixture", "owner", "digest", {},
                {"execution": self.execution}, 4 * 1024**2)

    def payload(self, phase="preflight"):
        plan = budgeted_plan({"phase": phase, "execution": copy.deepcopy(self.execution)})
        with self.db.transaction() as tx:
            allocation = bootstrap_roots.reserve(self.db, tx, self.row, phase, [self.slot])
        execution = bootstrap_roots.bind_execution(plan["execution"], allocation)
        grant = plan["budget_grant"]
        execution.update(phase=phase, execution_id=grant["execution_id"], budget_grant=grant,
            phase_deadline_boottime_ns=budget.phase_deadline_ns(grant) - grant["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS,
            bootstrap_unit="lhj-" + hashlib.sha256((grant["execution_id"] + ":bootstrap").encode()).hexdigest() + ".service",
            parent_mount_namespace="synthetic-parent-namespace")
        return {"execution": execution, "allocation": allocation}

    @contextlib.contextmanager
    def simulated_host(self, *, quota=None):
        real_readlink, real_access = os.readlink, os.access
        def readlink(path, *args, **kwargs):
            if str(path) == "/proc/self/ns/mnt": return "synthetic-isolated-namespace"
            return real_readlink(path, *args, **kwargs)
        def access(path, mode, *args, **kwargs):
            if str(path) in ("/tmp", "/var/tmp", "/dev/shm"): return False
            return real_access(path, mode, *args, **kwargs)
        def quota_observation(path, limit, *, expected_identity=None):
            info = Path(path).stat()
            self.assertEqual({"device": info.st_dev, "inode": info.st_ino, "uid": info.st_uid}, expected_identity)
            return {"project_id": info.st_ino, "hard_bytes": min(limit, 1024), "mount": {"source": "synthetic-device"}}
        with mock.patch.object(bootstrap.os, "readlink", side_effect=readlink), \
             mock.patch.object(bootstrap.os, "access", side_effect=access), \
             mock.patch.object(runner, "_mount_for", return_value={"options": "ro", "type": "ext4", "source": "synthetic-device"}), \
             mock.patch.object(runner, "_verify_cgroup_limits", return_value={"status": "LOGIC_ONLY"}), \
             mock.patch.object(runner, "_verify_project_quota", side_effect=quota or quota_observation):
            yield

    def plan_path(self, payload):
        return self.root / "evidence" / bootstrap.plan_name(payload["execution"]["execution_id"])

    def markers(self):
        return [self.root / name / ".lh-bootstrap-owner.json" for name in self.slot["roots"]]

    def test_fresh_preparation_then_business_reuses_marker_and_preserves_work(self):
        preflight = self.payload()
        with self.simulated_host(): self.assertEqual(0, bootstrap.prepare(preflight))
        markers = [path.read_bytes() for path in self.markers()]
        self.assertTrue(all(marker == markers[0] for marker in markers))
        self.assertEqual(0o400, stat.S_IMODE(self.plan_path(preflight).stat().st_mode))
        saved = json.loads(self.plan_path(preflight).read_bytes())
        self.assertEqual(preflight["allocation"], saved["bootstrap_allocation"])
        self.assertEqual(set(preflight["allocation"]["paths"]), set(saved["quota_observation"]))
        retained = self.root / "work" / "retained-output"
        retained.write_bytes(b"preflight evidence must survive")
        business = self.payload("business")
        with self.simulated_host(): self.assertEqual(0, bootstrap.prepare(business))
        self.assertEqual(markers, [path.read_bytes() for path in self.markers()])
        self.assertEqual(b"preflight evidence must survive", retained.read_bytes())
        self.assertTrue(self.plan_path(business).is_file())

    def test_dirty_fresh_root_is_detected_before_any_marker_is_written(self):
        payload = self.payload()
        dirty = self.root / "temporary" / "leftover"
        dirty.write_bytes(b"retained failure")
        with self.simulated_host(), self.assertRaises(JobError): bootstrap.prepare(payload)
        self.assertFalse(any(path.exists() for path in self.markers()))
        self.assertFalse(self.plan_path(payload).exists())
        self.assertEqual(b"retained failure", dirty.read_bytes())

    def test_wrong_business_marker_and_duplicate_plan_are_not_overwritten(self):
        preflight = self.payload()
        with self.simulated_host(): bootstrap.prepare(preflight)
        business = self.payload("business")
        with self.simulated_host(): bootstrap.prepare(business)
        original = self.plan_path(business).read_bytes()
        with self.simulated_host(), self.assertRaises(FileExistsError): bootstrap.prepare(business)
        self.assertEqual(original, self.plan_path(business).read_bytes())
        marker = self.markers()[0]
        marker.chmod(0o600)
        marker.write_bytes(b"another allocation")
        with self.simulated_host(), self.assertRaises(JobError): bootstrap.prepare(business)
        self.assertEqual(b"another allocation", marker.read_bytes())
        self.assertEqual(original, self.plan_path(business).read_bytes())

    def test_quota_identity_rejects_replaced_directory_and_parent_fallback(self):
        path = self.root / "work"
        identity = {key: self.slot["roots"]["work"][key] for key in ("device", "inode", "uid")}
        original = self.root / "original-work"
        path.rename(original)
        path.mkdir(mode=0o700)
        with mock.patch.object(runner, "_mount_for", return_value={"type": "ext4", "source": "synthetic-device"}), \
             mock.patch.object(runner.fcntl, "ioctl") as query:
            with self.assertRaises(runner.RunnerError): runner._verify_project_quota(path, 1024, expected_identity=identity)
            with self.assertRaises(runner.RunnerError): runner._verify_project_quota(path / "missing", 1024, expected_identity=identity)
        query.assert_not_called()
        self.assertFalse(any(original.iterdir()))
        self.assertFalse(any(path.iterdir()))

    def test_quota_failure_before_write_closes_all_roots_and_retains_primary(self):
        payload = self.payload()
        primary = KeyboardInterrupt("quota observation interrupted")
        real_close = os.close
        closed = []
        def close_then_fail(descriptor):
            closed.append(descriptor)
            real_close(descriptor)
            if len(closed) == 1: raise OSError("secondary close acknowledgement")
        def quota(*args, **kwargs): raise primary
        with self.simulated_host(quota=quota), mock.patch.object(bootstrap.os, "close", side_effect=close_then_fail):
            with self.assertRaises(KeyboardInterrupt) as failure: bootstrap.prepare(payload)
        self.assertIs(primary, failure.exception)
        self.assertEqual(3, len(closed))
        self.assertEqual(len(closed), len(set(closed)))
        self.assertFalse(any(path.exists() for path in self.markers()))
        for descriptor in closed:
            with self.assertRaises(OSError): os.fstat(descriptor)

    def test_marker_fsync_interruption_preserves_partial_marker_and_closes_all(self):
        payload = self.payload()
        primary = KeyboardInterrupt("marker fsync interrupted")
        real_close = os.close
        closed = []
        def close_then_fail(descriptor):
            closed.append(descriptor)
            real_close(descriptor)
            if len(closed) == 1: raise OSError("secondary marker close acknowledgement")
        with self.simulated_host(), mock.patch.object(bootstrap.os, "fsync", side_effect=primary), \
             mock.patch.object(bootstrap.os, "close", side_effect=close_then_fail):
            with self.assertRaises(KeyboardInterrupt) as failure: bootstrap.prepare(payload)
        self.assertIs(primary, failure.exception)
        self.assertEqual(4, len(closed))
        self.assertEqual(len(closed), len(set(closed)))
        self.assertEqual(1, sum(path.exists() for path in self.markers()))
        self.assertFalse(self.plan_path(payload).exists())
        with self.simulated_host(), self.assertRaises(JobError): bootstrap.prepare(payload)

    def test_plan_directory_fsync_failure_does_not_delete_or_replace_written_plan(self):
        payload = self.payload()
        real_fsync = os.fsync
        calls = []
        def fsync(descriptor):
            calls.append(descriptor)
            if len(calls) == 8: raise OSError("plan directory durability unknown")
            return real_fsync(descriptor)
        with self.simulated_host(), mock.patch.object(bootstrap.os, "fsync", side_effect=fsync):
            with self.assertRaisesRegex(OSError, "durability unknown"): bootstrap.prepare(payload)
        self.assertTrue(self.plan_path(payload).exists())
        before = self.plan_path(payload).read_bytes()
        with self.simulated_host(), self.assertRaises(JobError): bootstrap.prepare(payload)
        self.assertEqual(before, self.plan_path(payload).read_bytes())
        self.assertEqual(3, sum(path.exists() for path in self.markers()))

    def test_root_descriptor_identity_failure_survives_close_failure(self):
        path = self.root / "work"
        identity = {key: self.slot["roots"]["work"][key] for key in ("device", "inode", "uid")}
        identity["inode"] += 1
        real_close = os.close
        def close_then_fail(descriptor):
            real_close(descriptor)
            raise OSError("secondary close error")
        with mock.patch.object(bootstrap.os, "close", side_effect=close_then_fail):
            with self.assertRaises(JobError) as failure: bootstrap._root_descriptor(str(path), identity)
        self.assertEqual("IO_UNCERTAIN", failure.exception.code)


if __name__ == "__main__":
    unittest.main()
