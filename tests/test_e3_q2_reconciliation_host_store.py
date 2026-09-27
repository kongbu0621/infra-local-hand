"""Real retained host files; no remote transport, guest or authority changes."""
import errno
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from e3_host import q2_reconciliation_entry as entry
from e3_host import q2_reconciliation_io as io


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux noatime held-fd store")
class HostStoreIntegrity(unittest.TestCase):
    def setUp(self):
        home = Path.home()
        if any(os.stat(path).st_mode & 0o022 for path in (home, *home.parents)):
            self.skipTest("No protected local temporary parent")
        self.tmp = tempfile.TemporaryDirectory(prefix="q2-host-store-test-", dir=home)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.directory = self.root / "retained"
        self.guard = lambda: None

    def store(self, guard=None):
        store = entry.HostStore(str(self.directory), guard or self.guard)
        self.addCleanup(store.close)
        return store

    def test_guard_rejects_before_any_owned_persistent_write(self):
        def denied():
            raise ValueError("NO_JOINT_ADMISSION")
        with self.assertRaisesRegex(ValueError, "NO_JOINT_ADMISSION"):
            self.store(denied)
        self.assertFalse(self.directory.exists())

    def test_exact_files_remain_noatime_verified_across_core_and_bundle_writes(self):
        store = self.store()
        store.write("intent.json", b'{"status":"LIVE_ATTESTED"}\n')
        path = self.directory / "intent.json"
        before = io.metadata(path.stat())
        store.write("evidence-core.json", b'{"members":["intent.json"]}\n')
        store.write("q2-reconciliation-result.json.gz", b"compressed-example")
        store.check()
        self.assertEqual(before, io.metadata(path.stat()))
        self.assertEqual({"intent.json", "evidence-core.json", "q2-reconciliation-result.json.gz"}, set(store.files))
        self.assertEqual(len(store.files), len(store._opened))

    def test_prior_file_content_drift_blocks_next_core_write(self):
        store = self.store()
        store.write("intent.json", b"original")
        (self.directory / "intent.json").write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "HOST_FILE_CHANGED"):
            store.write("evidence-core.json", b"{}")
        self.assertFalse((self.directory / "evidence-core.json").exists())
        with self.assertRaisesRegex(ValueError, "HOST_STORE_UNUSABLE"):
            store.check()

    def test_same_bytes_different_inode_replacement_is_rejected(self):
        store = self.store()
        store.write("intent.json", b"original")
        substitute = self.root / "substitute"
        substitute.write_bytes(b"original")
        substitute.chmod(0o600)
        os.replace(substitute, self.directory / "intent.json")
        with self.assertRaisesRegex(ValueError, "METADATA_CHANGED|HOST_FILE_CHANGED"):
            store.check()

    def test_mode_and_hardlink_changes_block_later_seal(self):
        for mode in ("permissions", "hardlink"):
            with self.subTest(mode=mode):
                directory = self.root / mode
                store = entry.HostStore(str(directory), self.guard)
                try:
                    store.write("intent.json", b"original")
                    path = directory / "intent.json"
                    if mode == "permissions":
                        path.chmod(0o400)
                    else:
                        os.link(path, self.root / "alias")
                    with self.assertRaisesRegex(ValueError, "HOST_FILE_CHANGED"):
                        store.write("evidence-core.json", b"{}")
                    self.assertFalse((directory / "evidence-core.json").exists())
                finally:
                    store.close()

    def test_unrecognized_member_and_directory_substitution_are_rejected(self):
        store = self.store()
        store.write("intent.json", b"original")
        (self.directory / "unexpected").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "METADATA_CHANGED|HOST_MEMBERS_CHANGED"):
            store.check()
        store.close()
        second_path = self.root / "second"
        other = entry.HostStore(str(second_path), self.guard)
        self.addCleanup(other.close)
        second_path.rename(self.root / "retained-second")
        second_path.mkdir(mode=0o700)
        with self.assertRaisesRegex(ValueError, "METADATA_CHANGED|PATH_CHANGED"):
            other.check()

    def test_hash_not_only_length_is_checked_after_actual_write(self):
        store = self.store()
        real = os.write
        def corrupt(fd, raw):
            return real(fd, b"x" * len(raw))
        with patch.object(entry.os, "write", side_effect=corrupt), self.assertRaisesRegex(
                ValueError, "HOST_CONTENT_CHANGED"):
            store.write("intent.json", b"original")
        self.assertTrue((self.directory / "intent.json").exists())
        with self.assertRaisesRegex(ValueError, "HOST_STORE_UNUSABLE"):
            store.write("evidence-core.json", b"{}")

    def test_old_file_race_during_core_write_is_caught_before_return(self):
        store = self.store()
        store.write("intent.json", b"original")
        old_path = self.directory / "intent.json"
        real = os.write
        def race(fd, raw):
            result = real(fd, raw)
            old_path.write_bytes(b"modified")
            return result
        with patch.object(entry.os, "write", side_effect=race), self.assertRaisesRegex(
                ValueError, "HOST_FILE_CHANGED"):
            store.write("evidence-core.json", b"{}")
        self.assertTrue((self.directory / "evidence-core.json").exists())

    def test_renamed_current_file_during_write_is_caught_by_held_name_binding(self):
        store = self.store()
        real = os.write
        replaced = False
        def race(fd, raw):
            nonlocal replaced
            result = real(fd, raw)
            if not replaced:
                replaced = True
                path = self.directory / "intent.json"
                path.rename(self.directory / "moved.json")
                path.write_bytes(raw)
                path.chmod(0o600)
            return result
        with patch.object(entry.os, "write", side_effect=race), self.assertRaisesRegex(
                ValueError, "METADATA_CHANGED|HOST_FILE_CHANGED|HOST_MEMBERS_CHANGED"):
            store.write("intent.json", b"original")

    def test_short_write_is_retained_and_poisoned_without_overwrite(self):
        store = self.store()
        real = os.write
        with patch.object(entry.os, "write", side_effect=lambda fd, raw: real(fd, raw[:3])), \
                self.assertRaisesRegex(ValueError, "HOST_SHORT_WRITE"):
            store.write("intent.json", b"original")
        self.assertEqual(b"ori", (self.directory / "intent.json").read_bytes())
        with self.assertRaisesRegex(ValueError, "HOST_STORE_UNUSABLE"):
            store.write("intent.json", b"original")

    def test_fsync_failure_preserves_partial_and_never_allows_same_store_recovery(self):
        store = self.store()
        with patch.object(entry.os, "fsync", side_effect=OSError(errno.EIO, "fsync failed")), \
                self.assertRaises(OSError):
            store.write("intent.json", b"original")
        self.assertTrue((self.directory / "intent.json").exists())
        with self.assertRaisesRegex(ValueError, "HOST_STORE_UNUSABLE"):
            store.check()
        with self.assertRaises(FileExistsError):
            entry.HostStore(str(self.directory), self.guard)

    def test_held_read_has_no_noatime_fallback(self):
        real = os.open
        def denied(name, flags, *args, **kwargs):
            if name == self.directory.name and flags & os.O_NOATIME:
                raise OSError(errno.EPERM, "noatime denied")
            return real(name, flags, *args, **kwargs)
        with patch.object(entry.os, "open", side_effect=denied), self.assertRaises(PermissionError):
            self.store()
        self.assertTrue(self.directory.exists())
        self.assertEqual([], list(self.directory.iterdir()))

    def test_external_mutation_of_in_memory_manifest_is_rejected(self):
        store = self.store()
        store.write("intent.json", b"original")
        store.files["intent.json"] = b"modified"
        with self.assertRaisesRegex(ValueError, "HOST_MEMORY_CHANGED"):
            store.write("evidence-core.json", b"{}")

    def test_duplicate_name_cannot_overwrite(self):
        store = self.store()
        store.write("intent.json", b"original")
        with self.assertRaisesRegex(ValueError, "HOST_ALREADY_RETAINED"):
            store.write("intent.json", b"changed")
        self.assertEqual(b"original", (self.directory / "intent.json").read_bytes())

    def test_logical_size_limit_refuses_before_new_file_create(self):
        store = self.store()
        with patch.object(entry.delivery, "OUTPUT_LIMIT", 2), self.assertRaisesRegex(
                ValueError, "HOST_RETAIN_LIMIT"):
            store.write("intent.json", b"ninebytes")
        self.assertFalse((self.directory / "intent.json").exists())


if __name__ == "__main__":
    unittest.main()
