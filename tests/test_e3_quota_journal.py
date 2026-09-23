"""Real temporary-file persistence/locking plus LOGIC_ONLY launch callbacks.

No systemd service, quota syscall, host account, mount or privileged fixture is
created. Temporary control directories are under the test user's protected home,
since a writable /tmp ancestor is deliberately rejected by the production checks.
"""
from dataclasses import replace
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from admin.local_hand_quota_observer import admission as a, supervision as s
if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import journal as j
from test_e3_quota_monitor import fixture, encoded


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux control journal")
class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lhq-journal-test-", dir=Path.home())
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        info = self.directory.stat()
        self.arguments = dict(owner_uid=os.geteuid(), directory_device=info.st_dev,
                              directory_inode=info.st_ino)
        self.journal = j.StartJournal(self.directory, **self.arguments)
        self.addCleanup(self.journal.close)

    def binding(self, number=0, *, manifest_changes=None, slot_changes=None, **changes):
        value = fixture()
        value["boot_id"] = j._boot_id()
        value["max_query_ns"] = 30_000_000_000
        value.update(manifest_changes or {})
        slot = value["slots"][0]
        slot.update(ref="root-" + str(number), project_id=73 + number)
        slot["root"]["inode"] += number
        slot.update(slot_changes or {})
        raw = encoded(value)
        manifest = a.decode_manifest(raw, hashlib.sha256(raw).hexdigest())
        now = j._now()
        options = dict(slot_ref=slot["ref"], generation=slot["generation"], request_id=f"{number:032x}",
                       allocation_digest=f"{number:064x}", execution_id="2" * 32, phase="preflight",
                       now_ns=now, phase_deadline_ns=now + 30_000_000_000)
        options.update(changes)
        return s.bind_query(manifest, **options)

    def reopen(self):
        self.journal.close()
        self.journal = j.StartJournal(self.directory, **self.arguments)
        self.addCleanup(self.journal.close)

    def test_intent_is_durable_before_delivery_and_invocation_is_retained(self):
        binding = self.binding()
        calls = []
        original = os.fsync
        with mock.patch.object(j.os, "fsync", wraps=original) as sync:
            def callback(received):
                self.assertEqual(received, binding)
                self.assertGreaterEqual(sync.call_count, 2)
                self.assertEqual(self.journal.read(binding).status, "INTENT")
                calls.append(received.unit)
                self.journal.remember_invocation(binding, "a" * 32)
            delivery = self.journal.deliver_once(binding, callback)
        self.assertTrue(delivery.delivered)
        self.assertEqual(delivery.record.status, "INVOCATION_RECORDED")
        self.assertEqual(delivery.record.invocation_id, "a" * 32)
        self.assertEqual(hashlib.sha256(delivery.record.intent_json).hexdigest(), delivery.record.binding_digest)
        intent = json.loads(delivery.record.intent_json)
        self.assertEqual(intent["manifest_digest"], binding.manifest.digest)
        self.assertEqual(intent["root_inode"], binding.slot.root.inode)
        self.assertEqual(intent["project_id"], binding.slot.project_id)
        self.assertFalse(self.journal.deliver_once(binding, callback).delivered)
        self.reopen()
        self.assertEqual(self.journal.deliver_once(binding, callback).record, delivery.record)
        self.assertEqual(calls, [binding.unit])

    def test_failed_delivery_preserves_original_exception_and_blocks_replay(self):
        binding = self.binding()
        error = RuntimeError("synthetic delivery failed after possible acceptance")
        callback = mock.Mock(side_effect=error)
        with self.assertRaises(RuntimeError) as raised:
            self.journal.deliver_once(binding, callback)
        self.assertIs(raised.exception, error)
        self.assertEqual(self.journal.read(binding).status, "UNKNOWN")
        self.reopen()
        self.assertFalse(self.journal.deliver_once(binding, callback).delivered)
        callback.assert_called_once()

    def test_real_process_crash_before_ack_never_receives_recovery_launch(self):
        binding = self.binding()
        child = os.fork()
        if child == 0:
            try:
                with j.StartJournal(self.directory, **self.arguments) as journal:
                    journal.deliver_once(binding, lambda _: os._exit(19))
            except BaseException:
                os._exit(20)
            os._exit(21)
        deadline = time.monotonic() + 5
        waited, status = os.waitpid(child, os.WNOHANG)
        while waited == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
            waited, status = os.waitpid(child, os.WNOHANG)
        if waited == 0:
            os.kill(child, 9)
            os.waitpid(child, 0)
            self.fail("synthetic child did not reach its crash point within five seconds")
        self.assertEqual(waited, child)
        self.assertEqual(os.waitstatus_to_exitcode(status), 19)
        self.reopen()
        callback = mock.Mock()
        result = self.journal.deliver_once(binding, callback)
        callback.assert_not_called()
        self.assertFalse(result.delivered)
        self.assertEqual(result.record.status, "INTENT")
        self.assertIsNone(result.record.invocation_id)

    def test_same_request_cannot_change_any_fixed_binding(self):
        binding = self.binding()
        self.journal.deliver_once(binding, lambda _: None)
        for candidate in (replace(binding, deadline_ns=binding.deadline_ns - 1),
                          self.binding(request_id=binding.request_id, execution_id="3" * 32),
                          self.binding(request_id=binding.request_id, allocation_digest="e" * 64)):
            with self.subTest(candidate=candidate.execution_id), self.assertRaisesRegex(a.Rejected, "REQUEST_CONFLICT"):
                self.journal.deliver_once(candidate, mock.Mock())

    def test_allocation_and_resource_remain_reserved_across_requests(self):
        binding = self.binding()
        self.journal.deliver_once(binding, lambda _: None)
        self.journal.mark_unknown(binding, "RESPONSE_LOST")
        self.reopen()
        with self.assertRaisesRegex(a.Rejected, "ALLOCATION_RETAINED"):
            self.journal.deliver_once(self.binding(1, allocation_digest=binding.allocation_digest), mock.Mock())
        with self.assertRaisesRegex(a.Rejected, "RESOURCE_RETAINED"):
            self.journal.deliver_once(self.binding(request_id="b" * 32, allocation_digest="b" * 64), mock.Mock())
        with self.assertRaisesRegex(a.Rejected, "RESOURCE_RETAINED"):
            self.journal.deliver_once(self.binding(1, slot_changes={"ref": binding.slot.ref,
                                                                   "generation": "9" * 32}), mock.Mock())
        # A changed slot/ref/root still cannot reuse the same underlying project domain.
        candidate = self.binding(1, slot_changes={"project_id": binding.slot.project_id})
        with self.assertRaisesRegex(a.Rejected, "RESOURCE_RETAINED"):
            self.journal.deliver_once(candidate, mock.Mock())

    def test_unrecoverable_cgroup_length_is_rejected_before_persisting_or_delivering(self):
        binding = self.binding(manifest_changes={"cgroup_parent": "/" + "a" * 1019})
        callback = mock.Mock()
        with self.assertRaises(a.Rejected):
            self.journal.deliver_once(binding, callback)
        callback.assert_not_called()
        self.assertEqual([item.name for item in self.directory.iterdir()], ["lock"])

    def test_original_invocation_and_first_unknown_reason_cannot_be_replaced(self):
        binding = self.binding()
        self.journal.deliver_once(binding, lambda _: None)
        self.journal.remember_invocation(binding, "a" * 32)
        self.journal.remember_invocation(binding, "a" * 32)
        with self.assertRaisesRegex(a.Rejected, "ORIGINAL_RECORD_CONFLICT"):
            self.journal.remember_invocation(binding, "b" * 32)
        self.journal.mark_unknown(binding, "OUTPUT_MISSING")
        with self.assertRaisesRegex(a.Rejected, "ORIGINAL_RECORD_CONFLICT"):
            self.journal.mark_unknown(binding, "OTHER_FAILURE")
        self.reopen()
        record = self.journal.read(binding)
        self.assertEqual((record.invocation_id, record.unknown_reason), ("a" * 32, "OUTPUT_MISSING"))

    def test_fsync_failure_never_calls_delivery_and_existing_bytes_are_not_replayed(self):
        binding = self.binding()
        callback = mock.Mock()
        with mock.patch.object(j.os, "fsync", side_effect=OSError("synthetic fsync failure")):
            with self.assertRaises(OSError):
                self.journal.deliver_once(binding, callback)
        callback.assert_not_called()
        with self.assertRaisesRegex(a.Rejected, "JOURNAL_UNAVAILABLE"):
            self.journal.deliver_once(binding, callback)
        self.reopen()
        self.assertFalse(self.journal.deliver_once(binding, callback).delivered)
        callback.assert_not_called()

    def test_partial_intent_is_preserved_and_blocks_journal_recovery(self):
        binding = self.binding()
        original = os.write
        def short_write(fd, data):
            return original(fd, data[:17])
        callback = mock.Mock()
        with mock.patch.object(j.os, "write", side_effect=short_write):
            with self.assertRaisesRegex(a.Rejected, "CONTROL_SHORT_WRITE"):
                self.journal.deliver_once(binding, callback)
        callback.assert_not_called()
        self.assertEqual((self.directory / (binding.request_id + ".intent.json")).stat().st_size, 17)
        with self.assertRaises(a.Rejected):
            self.reopen()

    def test_directory_sync_failure_after_file_sync_never_delivers(self):
        binding = self.binding()
        callback = mock.Mock()
        original = os.fsync
        synced = []
        def fail_directory(fd):
            directory = stat.S_ISDIR(os.fstat(fd).st_mode)
            synced.append("directory" if directory else "file")
            if directory:
                raise OSError(errno.EIO, "synthetic directory fsync failure")
            original(fd)
        with mock.patch.object(j.os, "fsync", side_effect=fail_directory):
            with self.assertRaises(OSError):
                self.journal.deliver_once(binding, callback)
        self.assertEqual(synced, ["file", "directory"])
        callback.assert_not_called()
        self.reopen()
        self.assertFalse(self.journal.deliver_once(binding, callback).delivered)
        callback.assert_not_called()

    def test_lock_os_error_does_not_create_intent_or_call_delivery(self):
        callback = mock.Mock()
        with mock.patch.object(j.fcntl, "flock", side_effect=OSError(errno.EIO, "synthetic lock failure")):
            with self.assertRaises(OSError):
                self.journal.deliver_once(self.binding(), callback)
        callback.assert_not_called()
        self.assertEqual([item.name for item in self.directory.iterdir()], ["lock"])

    def test_uncertain_intent_close_is_not_retried_and_never_delivers(self):
        binding = self.binding()
        original = os.close
        closed, failed = [], []
        def close_once(fd):
            closed.append(fd)
            target = os.readlink(f"/proc/self/fd/{fd}")
            original(fd)
            if target.endswith(".intent.json") and not failed:
                failed.append(fd)
                raise OSError(errno.EINTR, "synthetic close already released descriptor")
        callback = mock.Mock()
        with mock.patch.object(j.os, "close", side_effect=close_once):
            with self.assertRaises(OSError):
                self.journal.deliver_once(binding, callback)
        self.assertEqual(len(failed), 1)
        self.assertEqual(closed.count(failed[0]), 1)
        callback.assert_not_called()
        self.reopen()
        self.assertFalse(self.journal.deliver_once(binding, callback).delivered)

    def test_uncertain_parent_close_closes_child_without_retry_or_leak(self):
        original = os.close
        closed = []
        def fail_first_close(fd):
            closed.append(fd)
            original(fd)
            if len(closed) == 1:
                raise OSError(errno.EINTR, "synthetic parent descriptor already released")
        with mock.patch.object(j.os, "close", side_effect=fail_first_close):
            with self.assertRaises(OSError):
                j.StartJournal(self.directory, **self.arguments)
        self.assertEqual(len(closed), 2)
        self.assertEqual(len(set(closed)), 2)
        for fd in closed:
            with self.assertRaises(OSError):
                os.fstat(fd)

    def test_uncertain_lock_close_poisons_handle_and_releases_thread_guard(self):
        original = os.close
        closed = []
        def fail_close(fd):
            closed.append(fd)
            original(fd)
            raise OSError(errno.EINTR, "synthetic lock close already released descriptor")
        with mock.patch.object(j.os, "close", side_effect=fail_close):
            with self.assertRaises(OSError):
                with self.journal._locked():
                    pass
        self.assertEqual(len(closed), 1)
        self.assertTrue(self.journal._guard.acquire(blocking=False))
        self.journal._guard.release()
        with self.assertRaisesRegex(a.Rejected, "JOURNAL_UNAVAILABLE"):
            self.journal.deliver_once(self.binding(), mock.Mock())

    def test_expired_boot_and_deadline_do_not_create_intents(self):
        binding = self.binding()
        callback = mock.Mock()
        with mock.patch.object(j, "_boot_id", return_value="99999999-9999-9999-9999-999999999999"):
            with self.assertRaisesRegex(a.Rejected, "BOOT_CHANGED"):
                self.journal.deliver_once(binding, callback)
        with mock.patch.object(j, "_now", return_value=binding.deadline_ns):
            with self.assertRaisesRegex(a.Rejected, "DEADLINE_EXPIRED"):
                self.journal.deliver_once(binding, callback)
        self.assertEqual([item.name for item in self.directory.iterdir()], ["lock"])
        callback.assert_not_called()

    def test_expiration_after_durable_intent_never_gets_a_second_chance(self):
        binding = self.binding()
        callback = mock.Mock()
        with mock.patch.object(j, "_now", side_effect=[binding.issued_ns, binding.deadline_ns]):
            with self.assertRaisesRegex(a.Rejected, "DEADLINE_EXPIRED"):
                self.journal.deliver_once(binding, callback)
        self.reopen()
        self.assertFalse(self.journal.deliver_once(binding, callback).delivered)
        callback.assert_not_called()

    def test_nonblocking_lock_prevents_second_controller_admission(self):
        binding = self.binding()
        with j.StartJournal(self.directory, **self.arguments) as other:
            with self.journal._locked():
                with self.assertRaisesRegex(a.Rejected, "JOURNAL_BUSY"):
                    other.deliver_once(binding, mock.Mock())
            self.assertTrue(other.deliver_once(binding, lambda _: None).delivered)
        self.assertFalse(self.journal.deliver_once(binding, mock.Mock()).delivered)

    def test_capacity_remains_bounded_and_existing_record_is_readable_when_full(self):
        first = self.binding()
        self.journal.deliver_once(first, lambda _: None)
        for number in range(1, j.MAX_INTENTS):
            self.journal.deliver_once(self.binding(number), lambda _: None)
        with self.assertRaisesRegex(a.Rejected, "JOURNAL_CAPACITY"):
            self.journal.deliver_once(self.binding(j.MAX_INTENTS), mock.Mock())
        self.assertFalse(self.journal.deliver_once(first, mock.Mock()).delivered)
        self.assertEqual(len(list(self.directory.iterdir())), 1 + j.MAX_INTENTS)

    def test_symlink_wrong_identity_unsafe_directory_and_unsafe_ancestor_rejected(self):
        with self.assertRaisesRegex(a.Rejected, "CONTROL_IDENTITY"):
            j.StartJournal(self.directory, **dict(self.arguments, directory_inode=self.arguments["directory_inode"] + 1))
        self.journal.close()
        self.directory.chmod(0o750)
        with self.assertRaisesRegex(a.Rejected, "CONTROL_DIRECTORY_PRIVATE"):
            j.StartJournal(self.directory, **self.arguments)
        self.directory.chmod(0o700)
        link = self.directory / "link"
        link.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises(OSError):
            j.StartJournal(link, **self.arguments)
        link.unlink()
        child = self.directory / "child"
        child.mkdir(mode=0o700)
        info = child.stat()
        self.directory.chmod(0o777)
        with self.assertRaisesRegex(a.Rejected, "CONTROL_ANCESTRY"):
            j.StartJournal(child, owner_uid=os.geteuid(), directory_device=info.st_dev, directory_inode=info.st_ino)
        self.directory.chmod(0o700)

    def test_control_path_is_readonly_and_recheck_rejects_directory_replacement(self):
        self.assertEqual(self.journal.control_dir, str(self.directory))
        with self.assertRaises(AttributeError):
            self.journal.control_dir = "/other"
        self.journal.verify_directory()
        moved = self.directory.with_name(self.directory.name + "-moved")
        self.directory.rename(moved)
        try:
            self.directory.mkdir(mode=0o700)
            with self.assertRaisesRegex(a.Rejected, "CONTROL_IDENTITY"):
                self.journal.verify_directory()
        finally:
            self.directory.rmdir()
            moved.rename(self.directory)

    def test_symlink_fifo_hardlink_and_permissive_record_fail_without_delivery(self):
        binding = self.binding()
        target = self.directory / (binding.request_id + ".intent.json")
        for kind in ("symlink", "fifo", "hardlink", "mode"):
            with self.subTest(kind=kind):
                if kind == "symlink":
                    target.symlink_to("lock")
                elif kind == "fifo":
                    os.mkfifo(target, 0o600)
                elif kind == "hardlink":
                    os.link(self.directory / "lock", target)
                else:
                    target.write_bytes(b"{}\n")
                    target.chmod(0o644)
                callback = mock.Mock()
                with self.assertRaises((OSError, a.Rejected)):
                    self.journal.deliver_once(binding, callback)
                callback.assert_not_called()
                target.unlink()

    def test_unknown_files_and_orphan_invocations_block_admission(self):
        callback = mock.Mock()
        rogue = self.directory / "unexpected"
        rogue.write_bytes(b"x")
        with self.assertRaisesRegex(a.Rejected, "CONTROL_UNKNOWN_FILE"):
            self.journal.deliver_once(self.binding(), callback)
        rogue.unlink()
        rogue = self.directory / ("f" * 32 + ".invocation.json")
        rogue.write_bytes(j._encode({"schema": "irrelevant"}))
        rogue.chmod(0o600)
        with self.assertRaisesRegex(a.Rejected, "ORPHAN_RECORD"):
            self.journal.deliver_once(self.binding(), callback)
        callback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
