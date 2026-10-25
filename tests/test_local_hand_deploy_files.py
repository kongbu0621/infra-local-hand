"""Real file identity and process-interruption checks for deployment file actions."""
import copy
import errno
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from admin.local_hand_deploy import files


ROOT = Path(__file__).resolve().parents[1]


class DeploymentFiles(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        self.source = self.write("candidate", b"candidate\n")
        self.target = self.write("configuration", b"original\n")
        self.lock = os.open(self.root / "node.lock", os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, self.lock)
        fcntl.flock(self.lock, fcntl.LOCK_EX)
        try:
            files._binding(self.lock)
        except files.FileError as error:
            if error.code == "UNSUPPORTED":
                self.skipTest(str(error))
            raise

    def write(self, name, data, mode=0o600):
        path = self.root / name
        path.write_bytes(data)
        path.chmod(mode)
        return path

    def plan(self, **options):
        spec = {"source": str(self.source), "target": str(self.target)}
        attributes = options.pop("attributes", {})
        return files.plan_files([dict(spec, **attributes)], **options)["files"][0]

    def prepare(self, plan=None, attempt="publish"):
        return files.prepare_file(plan or self.plan(), self.state,
                                  operation_id="operation", attempt_id=attempt,
                                  lock_fd=self.lock)

    def restore(self, prepared, state=None, operation="operation"):
        return files.prepare_restore(prepared, state or self.state,
                                     operation_id=operation, attempt_id="restore",
                                     lock_fd=self.lock)

    def child(self, action, boundary):
        # This intent is outside adapter staging, as the real coordinator's
        # SQLite record is.  Both the intent and its containing directory sync.
        intent = self.write("saved-intent.json", json.dumps(action).encode())
        fd = os.open(intent, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        os.fsync(directory)
        os.close(directory)
        code = r'''
import json, os, sys
from admin.local_hand_deploy import files
action = json.load(open(sys.argv[1]))
boundary = sys.argv[3]
if boundary in ('rename', 'unlink'):
    original = getattr(files.os, boundary)
    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        os._exit(73)
    setattr(files.os, boundary, interrupted)
files.execute_file(action, lock_fd=int(sys.argv[2]))
os._exit(74)
'''
        env = dict(os.environ, PYTHONPATH=str(ROOT / "tools"))
        return subprocess.run([sys.executable, "-c", code, str(intent), str(self.lock), boundary],
                              env=env, pass_fds=(self.lock,), capture_output=True,
                              timeout=15)

    def test_plan_is_read_only_and_serializable(self):
        before = {p.name: (p.stat().st_ino, p.read_bytes()) for p in self.root.iterdir() if p.is_file()}
        plan = self.plan()
        json.loads(json.dumps(plan))
        after = {p.name: (p.stat().st_ino, p.read_bytes()) for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(list(self.state.iterdir()), [])
        self.assertEqual(set(plan["original"]["binding"]), {"filesystem_id", "handle_type", "handle"})

    def test_explicit_remove_is_durable_and_restorable(self):
        entry = files.plan_files([{"target": str(self.target), "remove": True}])["files"][0]
        prepared = self.prepare(entry)
        self.assertEqual("delete", prepared["action"])
        self.assertEqual(b"original\n", self.target.read_bytes())
        files.execute_file(prepared, lock_fd=self.lock)
        self.assertFalse(self.target.exists())
        restored = self.restore(prepared)
        files.execute_file(restored, lock_fd=self.lock)
        self.assertEqual(b"original\n", self.target.read_bytes())

    def test_removing_missing_target_is_noop(self):
        self.target.unlink()
        entry = files.plan_files([{"target": str(self.target), "remove": True}])["files"][0]
        prepared = self.prepare(entry)
        self.assertEqual("noop", prepared["action"])
        self.assertEqual([], list(self.state.iterdir()))

    def test_publish_reuse_restore_and_reuse(self):
        action = self.prepare()
        json.loads(json.dumps(action))
        self.assertEqual(files.observe_file(action)["state"], "original")
        backup = Path(action["backup"]["path"])
        self.assertEqual(backup.read_bytes(), b"original\n")
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertTrue(files.execute_file(action, lock_fd=self.lock)["changed"])
        publication_inode = self.target.stat().st_ino
        self.assertFalse(files.execute_file(action, lock_fd=self.lock)["changed"])
        self.assertEqual(self.target.stat().st_ino, publication_inode)
        restore = self.restore(action)
        self.assertTrue(files.execute_file(restore, lock_fd=self.lock)["changed"])
        restored_inode = self.target.stat().st_ino
        self.assertEqual(self.target.read_bytes(), b"original\n")
        self.assertEqual(files.observe_file(restore)["state"], "target")
        # Restored bytes do not re-create the original object's identity.
        self.assertEqual(files.observe_file(action)["state"], "conflict")
        self.assertFalse(files.execute_file(restore, lock_fd=self.lock)["changed"])
        self.assertEqual(self.target.stat().st_ino, restored_inode)

    def test_exact_target_is_noop_and_does_not_prepare_or_sync(self):
        self.source.write_bytes(self.target.read_bytes())
        action = self.prepare()
        self.assertEqual(action["action"], "noop")
        self.assertEqual(files.observe_file(action)["proof"], "original_identity")
        self.assertEqual(list(self.state.iterdir()), [])
        with mock.patch.object(files.os, "rename", side_effect=AssertionError("unexpected rename")), \
                mock.patch.object(files.os, "fsync", side_effect=AssertionError("unexpected sync")):
            self.assertFalse(files.execute_file(action, lock_fd=self.lock)["changed"])

    def test_mode_only_change_is_an_effect_and_restores_original_mode(self):
        self.source.write_bytes(self.target.read_bytes())
        action = self.prepare(self.plan(attributes={"mode": 0o640}))
        self.assertEqual(action["action"], "replace")
        files.execute_file(action, lock_fd=self.lock)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o640)
        files.execute_file(self.restore(action), lock_fd=self.lock)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)

    def test_original_absence_delete_and_observed_absence(self):
        self.target.unlink()
        action = self.prepare()
        self.assertEqual(action["original"], {"exists": False})
        self.assertIsNone(action["backup"])
        files.execute_file(action, lock_fd=self.lock)
        restore = self.restore(action)
        self.assertEqual(restore["action"], "delete")
        files.execute_file(restore, lock_fd=self.lock)
        self.assertFalse(self.target.exists())
        self.assertEqual(files.observe_file(restore)["proof"], "satisfied_observed")
        with mock.patch.object(files.os, "unlink", side_effect=AssertionError("repeated deletion")):
            self.assertFalse(files.execute_file(restore, lock_fd=self.lock)["changed"])

    def test_not_published_original_absence_can_be_rolled_back_as_noop(self):
        self.target.unlink()
        action = self.prepare()
        restore = self.restore(action)
        self.assertEqual(restore["action"], "noop")
        self.assertFalse(files.execute_file(restore, lock_fd=self.lock)["changed"])

    def test_same_content_independent_replacement_is_not_owned(self):
        action = self.prepare()
        files.execute_file(action, lock_fd=self.lock)
        independent = self.write("independent", self.target.read_bytes())
        os.replace(independent, self.target)
        self.assertEqual(files.observe_file(action)["state"], "conflict")
        with self.assertRaises(files.FileError) as raised:
            self.restore(action)
        self.assertEqual(raised.exception.code, "CONFLICT")

    def test_target_mode_drift_is_not_a_noop(self):
        action = self.prepare()
        self.target.chmod(0o640)
        self.assertEqual(files.observe_file(action)["state"], "conflict")
        with self.assertRaises(files.FileError):
            files.execute_file(action, lock_fd=self.lock)

    def test_parent_identity_and_mode_are_checked(self):
        action = self.prepare()
        self.root.chmod(0o750)
        self.assertEqual(files.observe_file(action)["state"], "conflict")
        self.root.chmod(0o700)
        altered = copy.deepcopy(action)
        altered["parent"]["binding"]["filesystem_id"] += 1
        self.assertEqual(files.observe_file(altered)["state"], "conflict")

    def test_dangling_symlink_and_hardlink_are_not_missing(self):
        self.target.unlink()
        self.target.symlink_to("does-not-exist")
        with self.assertRaises(files.FileError) as raised:
            self.plan()
        self.assertEqual(raised.exception.code, "CONFLICT")
        self.target.unlink()
        os.link(self.source, self.target)
        with self.assertRaises(files.FileError):
            self.plan()

    def test_source_identity_is_rechecked_before_preparing(self):
        plan = self.plan()
        replacement = self.write("replacement", self.source.read_bytes())
        os.replace(replacement, self.source)
        with self.assertRaises(files.FileError):
            self.prepare(plan)
        self.assertEqual(list(self.state.iterdir()), [])

    def test_directory_symlink_is_rejected(self):
        (self.root / "alias").symlink_to(self.state, target_is_directory=True)
        with self.assertRaises(files.FileError):
            files.prepare_file(self.plan(), self.root / "alias", operation_id="operation",
                               attempt_id="publish", lock_fd=self.lock)

    def test_no_lock_and_wrong_lock_cannot_publish(self):
        action = self.prepare()
        other = os.open(self.root / "other.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            with self.assertRaises(files.FileError) as raised:
                files.execute_file(action, lock_fd=other)
            self.assertEqual(raised.exception.code, "LOCK_REQUIRED")
            fcntl.flock(other, fcntl.LOCK_EX)
            with self.assertRaises(files.FileError) as raised:
                files.execute_file(action, lock_fd=other)
            self.assertEqual(raised.exception.code, "CONFLICT")
        finally:
            os.close(other)
        self.assertEqual(self.target.read_bytes(), b"original\n")

    def test_new_descriptor_to_same_durable_lock_can_resume(self):
        action = self.prepare()
        fcntl.flock(self.lock, fcntl.LOCK_UN)
        other = os.open(self.root / "node.lock", os.O_RDWR)
        try:
            fcntl.flock(other, fcntl.LOCK_EX)
            files.execute_file(json.loads(json.dumps(action)), lock_fd=other)
        finally:
            os.close(other)
        fcntl.flock(self.lock, fcntl.LOCK_EX)

    def test_max_file_bytes_rejects_before_content_read(self):
        with mock.patch.object(files.os, "read", side_effect=AssertionError("must not read oversized file")):
            with self.assertRaises(files.FileError) as raised:
                self.plan(limits=files.FileLimits(max_file_bytes=2))
        self.assertEqual(raised.exception.code, "LIMIT_EXCEEDED")

    def test_file_count_rejects_before_open(self):
        specs = [dict(target=str(self.target), source=str(self.source))] * 2
        with mock.patch.object(files.os, "open", side_effect=AssertionError("must not open")):
            with self.assertRaises(files.FileError) as raised:
                files.plan_files(specs, limits=files.FileLimits(max_files=1))
        self.assertEqual(raised.exception.code, "LIMIT_EXCEEDED")

    def test_total_budget_reserves_compensation_and_bounds_source_read(self):
        with self.assertRaises(files.FileError) as raised:
            self.plan(limits=files.FileLimits(max_total_bytes=18))
        self.assertEqual(raised.exception.code, "LIMIT_EXCEEDED")
        self.assertEqual(list(self.state.iterdir()), [])

    def test_partial_preparation_retained_and_complete_retry_works(self):
        plan = self.plan()
        real_write = os.write
        calls = 0
        def partial(fd, data):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(fd, data[:2])
            raise OSError(errno.ENOSPC, "injected preparation disk-full")
        with mock.patch.object(files.os, "write", side_effect=partial):
            with self.assertRaises(OSError):
                self.prepare(plan)
        partials = list(self.state.iterdir())
        self.assertEqual(len(partials), 1)
        self.assertEqual(partials[0].read_bytes(), b"or")
        action = self.prepare(plan, "retry")
        self.assertEqual(partials[0].read_bytes(), b"or")
        files.execute_file(action, lock_fd=self.lock)
        self.assertEqual(self.target.read_bytes(), b"candidate\n")

    def test_failed_preparation_objects_count_toward_file_budget(self):
        for index in range(2):
            path = self.state / f"failed-{index}"
            path.write_bytes(b"")
            path.chmod(0o600)
        with self.assertRaises(files.FileError) as raised:
            self.prepare(self.plan(limits=files.FileLimits(max_preparation_files=2)))
        self.assertEqual(raised.exception.code, "LIMIT_EXCEEDED")

    def test_backup_rename_sync_failure_is_reused_and_resynced(self):
        plan = self.plan()
        real_sync, calls = os.fsync, 0
        def failing(fd):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError(errno.EIO, "injected backup rename directory sync")
            return real_sync(fd)
        with mock.patch.object(files.os, "fsync", side_effect=failing):
            with self.assertRaises(OSError):
                self.prepare(plan)
        backup = next(self.state.glob("original-*"))
        identity = backup.stat().st_ino
        action = self.prepare(plan, "retry")
        self.assertEqual(Path(action["backup"]["path"]).stat().st_ino, identity)
        self.assertEqual(backup.read_bytes(), b"original\n")

    def test_backup_content_and_identity_are_checked_before_restore(self):
        action = self.prepare()
        files.execute_file(action, lock_fd=self.lock)
        backup = Path(action["backup"]["path"])
        replacement = self.write("replacement", backup.read_bytes())
        os.replace(replacement, backup)
        with self.assertRaises(files.FileError) as raised:
            self.restore(action)
        self.assertEqual(raised.exception.code, "CONFLICT")
        self.assertEqual(self.target.read_bytes(), b"candidate\n")

    def test_restore_distinct_state_keeps_original_retention_in_budget(self):
        action = self.prepare()
        files.execute_file(action, lock_fd=self.lock)
        new_state = self.root / "restore-state"
        new_state.mkdir(mode=0o700)
        action["preparation_budget_bytes"] = action["original"]["size"]
        action["preparation_reservations"] = {action["namespace"]: action["preparation_budget_bytes"]}
        with self.assertRaises(files.FileError) as raised:
            self.restore(action, new_state, "successor")
        self.assertEqual(raised.exception.code, "LIMIT_EXCEEDED")

    def test_real_process_dies_after_publication_before_sync(self):
        action = self.prepare()
        result = self.child(action, "rename")
        self.assertEqual(result.returncode, 73, result.stderr)
        identity = self.target.stat().st_ino
        self.assertEqual(files.observe_file(action)["state"], "target")
        with mock.patch.object(files.os, "rename", side_effect=AssertionError("must only sync")):
            observed = files.execute_file(json.loads(json.dumps(action)), lock_fd=self.lock)
        self.assertFalse(observed["changed"])
        self.assertEqual(self.target.stat().st_ino, identity)

    def test_real_process_dies_after_restore_rename(self):
        action = self.prepare()
        files.execute_file(action, lock_fd=self.lock)
        restore = self.restore(action)
        result = self.child(restore, "rename")
        self.assertEqual(result.returncode, 73, result.stderr)
        identity = self.target.stat().st_ino
        with mock.patch.object(files.os, "rename", side_effect=AssertionError("must not restore twice")):
            files.execute_file(json.loads(json.dumps(restore)), lock_fd=self.lock)
        self.assertEqual(self.target.stat().st_ino, identity)
        self.assertEqual(self.target.read_bytes(), b"original\n")

    def test_real_process_dies_after_delete(self):
        self.target.unlink()
        action = self.prepare()
        files.execute_file(action, lock_fd=self.lock)
        restore = self.restore(action)
        result = self.child(restore, "unlink")
        self.assertEqual(result.returncode, 73, result.stderr)
        with mock.patch.object(files.os, "unlink", side_effect=AssertionError("must not delete twice")):
            observed = files.execute_file(json.loads(json.dumps(restore)), lock_fd=self.lock)
        self.assertEqual(observed["proof"], "satisfied_observed")

    def test_real_process_report_loss_does_not_repeat_completed_effect(self):
        action = self.prepare()
        result = self.child(action, "report")
        self.assertEqual(result.returncode, 74, result.stderr)
        identity = self.target.stat().st_ino
        self.assertFalse(files.execute_file(action, lock_fd=self.lock)["changed"])
        self.assertEqual(self.target.stat().st_ino, identity)

    def test_unsupported_handles_never_fall_back_to_inode(self):
        with mock.patch.object(files, "_binding", side_effect=files.FileError("UNSUPPORTED", "test unsupported")):
            with self.assertRaises(files.FileError) as raised:
                self.plan()
        self.assertEqual(raised.exception.code, "UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
