"""Real local temporary files, never a guest or Q2 acceptance surrogate."""
import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

from e3_host import q2_reconciliation_io as io
from e3_host import q2_reconciliation_records as records


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux protected no-atime IO")
class ProtectedFiles(unittest.TestCase):
    def setUp(self):
        # /tmp and the Work workspace have writable ancestors. They correctly
        # fail the production walker; use the caller's protected home for tests.
        home = Path.home()
        if any(os.stat(p).st_mode & 0o022 for p in (home, *home.parents)):
            self.skipTest("No protected local temporary parent")
        self.tmp = tempfile.TemporaryDirectory(prefix="q2-reconciliation-test-", dir=home)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.guard = lambda: None

    def file(self, name="old.json", raw=b'{"key":"value"}\n'):
        path = self.root / name
        path.write_bytes(raw)
        path.chmod(0o600)
        return path

    def docs(self):
        return {name: records.encoded({"document": name, "plan": "a" * 64})
                for name in records.DOCUMENT_NAMES}

    def test_full_metadata_content_and_atime_preserved_and_held_reverified(self):
        path = self.file()
        before = io.metadata(path.stat())
        expected = dict(sha256=hashlib.sha256(b'{"key":"value"}\n').hexdigest(),
                        bytes=16, source_metadata=before)
        with io.read_pinned(path, self.guard, expected) as held:
            self.assertEqual(b'{"key":"value"}\n', held.data)
            self.assertEqual(before, io.verify_held(held))
            self.assertEqual(before, io.metadata(path.stat()))
        self.assertEqual(before, io.metadata(path.stat()))

    def test_pin_mismatch_does_not_change_access_time(self):
        path = self.file()
        before = io.metadata(path.stat())
        with self.assertRaisesRegex(ValueError, "PIN_DIGEST"):
            io.read_pinned(path, self.guard, {"sha256": "0" * 64})
        self.assertEqual(before, io.metadata(path.stat()))

    @unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() == 0, "Real ordinary-owner chown requires root")
    def test_only_explicit_fixed_ordinary_owner_can_be_scanned(self):
        folder = self.root / "ordinary"
        folder.mkdir(mode=0o700)
        path = self.file("ordinary/ledger.json")
        try:
            os.chown(folder, 50001, 50001)
            os.chown(path, 50001, 50001)
        except OSError as error:
            if error.errno in (errno.EINVAL, errno.EPERM):
                self.skipTest("Current root namespace cannot map/chown ordinary UID 50001")
            raise
        before = io.metadata(path.stat())
        with self.assertRaisesRegex(ValueError, "UNPROTECTED_PATH"):
            io.read_pinned(path, self.guard)
        with io.read_pinned(path, self.guard, allowed_uids={0, 50001}) as held:
            self.assertEqual(before, held.verify())
        observed = io.snapshot(folder, self.guard, allowed_uids={0, 50001})
        self.assertEqual(2, observed["inodes"])
        self.assertEqual({50001}, {row["source_metadata"]["uid"] for row in observed["entries"]})
        with self.assertRaisesRegex(ValueError, "UNPROTECTED_PATH"):
            io.snapshot(folder, self.guard, allowed_uids={0, 50002})

    def test_allowed_owners_remain_explicit_bounded_integers(self):
        self.assertEqual(frozenset({0, 50001}), io.allowed_owners({0, 50001}))
        for owners in ([], [True], [2**32 - 1], ["0"], list(range(17))):
            with self.assertRaisesRegex(ValueError, "OWNER_SET"):
                io.allowed_owners(owners)

    def test_actual_allocation_complete_tree_and_cross_root_dedup(self):
        folder = self.root / "tree"
        folder.mkdir(mode=0o700)
        path = self.file("tree/old.json")
        seen = set()
        value = io.snapshot(folder, self.guard, seen=seen)
        self.assertEqual(2, value["inodes"])
        self.assertEqual(sum(p.stat().st_blocks * 512 for p in (folder, path)), value["bytes"])
        self.assertEqual([".", "old.json"], [row["relative_path"] for row in value["entries"]])
        self.assertEqual(value, io.snapshot(folder, self.guard, expected=value))
        duplicate = io.snapshot(path, self.guard, seen=seen)
        self.assertEqual((0, 0), (duplicate["bytes"], duplicate["inodes"]))
        self.assertEqual(1, len(duplicate["entries"]))

    def test_unknown_or_missing_expected_member_rejected(self):
        folder = self.root / "tree"
        folder.mkdir(mode=0o700)
        self.file("tree/old.json")
        value = io.snapshot(folder, self.guard)
        for entries in (value["entries"][:1], value["entries"] + [dict(value["entries"][0])]):
            with self.assertRaises(ValueError):
                io.snapshot(folder, self.guard, expected=entries)

    def test_hardlink_and_world_writable_ancestor_rejected(self):
        path = self.file()
        os.link(path, self.root / "alias")
        with self.assertRaisesRegex(ValueError, "OBJECT_TYPE"):
            io.read_pinned(path, self.guard)
        self.root.chmod(0o777)
        with self.assertRaisesRegex(ValueError, "UNPROTECTED_PATH"):
            io.read_pinned(path, self.guard)
        self.root.chmod(0o700)

    def test_other_device_member_rejected_before_content_open(self):
        self.file()
        real_stat, real_open = os.stat, os.open
        opened = []
        def changed(name, *args, **kwargs):
            value = real_stat(name, *args, **kwargs)
            if name == "old.json":
                fields = list(value)
                fields[2] += 1
                return os.stat_result(fields)
            return value
        def tracked(name, *args, **kwargs):
            opened.append(name)
            return real_open(name, *args, **kwargs)
        with patch.object(io.os, "stat", side_effect=changed), patch.object(io.os, "open", side_effect=tracked):
            with self.assertRaisesRegex(ValueError, "DEVICE_CHANGED"):
                io.snapshot(self.root, self.guard)
        self.assertNotIn("old.json", opened)

    def test_symlink_ancestor_and_lexical_alias_rejected(self):
        path = self.file()
        (self.root / "alias").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            io.read_pinned(self.root / "alias" / path.name, self.guard)
        for name in (str(path) + "/", str(self.root) + "/./old.json", "//root/example"):
            with self.assertRaisesRegex(ValueError, "PATH_ALIAS"):
                io.read_pinned(name, self.guard)

    def test_open_noatime_denial_has_no_unprotected_retry(self):
        path = self.file()
        real = os.open
        calls = []
        def denied(name, flags, *args, **kwargs):
            calls.append(flags)
            if name == path.name:
                raise OSError(errno.EPERM, "noatime denied")
            return real(name, flags, *args, **kwargs)
        with patch.object(io.os, "open", side_effect=denied), self.assertRaises(PermissionError):
            io.read_pinned(path, self.guard)
        self.assertTrue(all(value & os.O_NOATIME for value in calls if not value & os.O_PATH))

    def test_file_replacement_after_fd_read_is_detected(self):
        path = self.file()
        replacement = self.file("replacement.json", b'{"key":"other"}\n')
        real = os.read
        mutated = False
        def racing(fd, count):
            nonlocal mutated
            raw = real(fd, count)
            if raw and not mutated:
                mutated = True
                os.replace(replacement, path)
            return raw
        with patch.object(io.os, "read", side_effect=racing), self.assertRaisesRegex(
                ValueError, "CONTENT_CHANGED|METADATA_CHANGED|PATH_CHANGED"):
            io.read_pinned(path, self.guard)

    def test_content_and_mode_drift_after_read_are_rejected(self):
        path = self.file()
        with io.read_pinned(path, self.guard) as held:
            path.write_bytes(b'{"key":"other"}\n')
            with self.assertRaisesRegex(ValueError, "METADATA_CHANGED"):
                io.verify_held(held)
        with io.read_pinned(path, self.guard) as held:
            path.chmod(0o400)
            with self.assertRaisesRegex(ValueError, "METADATA_CHANGED"):
                io.verify_held(held)

    def test_directory_renaming_after_open_rejected(self):
        tree = self.root / "tree"
        tree.mkdir(mode=0o700)
        self.file("tree/old.json")
        with io.read_pinned(tree / "old.json", self.guard) as held:
            tree.rename(self.root / "retained")
            tree.mkdir(mode=0o700)
            with self.assertRaisesRegex(ValueError, "METADATA_CHANGED|PATH_CHANGED"):
                held.verify()

    def test_authorized_sibling_creation_does_not_claim_ancestor_times_preserved(self):
        path = self.file()
        with io.read_pinned(path, self.guard) as held:
            before = dict(held.metadata)
            (self.root / "new-record").mkdir(mode=0o700)
            self.assertEqual(before, held.verify())

    def test_ancestor_permission_change_still_blocks_held_read(self):
        path = self.file()
        with io.read_pinned(path, self.guard) as held:
            self.root.chmod(0o750)
            with self.assertRaisesRegex(ValueError, "METADATA_CHANGED"):
                held.verify()
            self.root.chmod(0o700)

    def test_link_is_rejected_before_readlink_on_relatime_mount(self):
        link = self.root / "link"
        link.symlink_to("old.json")
        self.file()
        expected = [dict(relative_path="link", type="symlink", link_target="old.json",
                         source_metadata=io.metadata(link.lstat()))]
        # There is no fd NOATIME guarantee for readlink on a relatime mount.
        geometry = os.statvfs(self.root)
        if geometry.f_flag & getattr(os, "ST_NOATIME", 1024):
            self.skipTest("Local test mount already has symlink noatime")
        with patch.object(io.os, "readlink", side_effect=AssertionError("unsafe link read")) as readlink:
            with self.assertRaisesRegex(ValueError, "SYMLINK_NOATIME_UNSUPPORTED"):
                io.snapshot(self.root, self.guard, expected=expected)
            readlink.assert_not_called()

    def test_symlink_without_exact_target_pin_is_rejected(self):
        (self.root / "link").symlink_to("missing")
        with self.assertRaisesRegex(ValueError, "SYMLINK_UNPINNED"):
            io.snapshot(self.root, self.guard)

    def test_exclusive_durable_five_files_and_readonly_same_value_replay(self):
        docs = self.docs()
        directory = self.root / "record"
        result = records.write_once(directory, docs, self.guard)
        self.assertFalse(result["replay"])
        self.assertFalse(result["allow_run"])
        self.assertEqual(6, result["allocation"]["inodes"])
        self.assertEqual(set(records.LIMITS), {p.name for p in directory.iterdir()})
        # Ordinary test inspection can update directory atime; snapshot it now.
        before = io.snapshot(directory, self.guard)
        with patch.object(records.os, "write", side_effect=AssertionError("replayed write")), \
                patch.object(records.os, "fsync", side_effect=AssertionError("replayed fsync")):
            replay = records.write_once(directory, docs, self.guard)
            self.assertTrue(replay["replay"])
            self.assertFalse(replay["allow_run"])
        self.assertEqual(before, io.snapshot(directory, self.guard))

    def test_different_replay_and_added_alias_fail_retaining_original(self):
        docs = self.docs()
        directory = self.root / "record"
        records.write_once(directory, docs, self.guard)
        changed = dict(docs)
        changed[records.DOCUMENT_NAMES[0]] = b'{"changed":true}\n'
        with self.assertRaisesRegex(ValueError, "RECORD_CHANGED"):
            records.write_once(directory, changed, self.guard)
        os.link(directory / records.DOCUMENT_NAMES[0], self.root / "alias")
        with self.assertRaisesRegex(ValueError, "OBJECT_TYPE|RECORD_CHANGED"):
            records.verify_sealed(directory, docs, self.guard)

    def test_partial_directory_is_not_repaired_or_reused(self):
        directory = self.root / "record"
        directory.mkdir(mode=0o700)
        partial = directory / records.DOCUMENT_NAMES[0]
        partial.write_bytes(b'{"partial":')
        partial.chmod(0o600)
        before = partial.read_bytes()
        with self.assertRaisesRegex(ValueError, "PARTIAL_RETAINED"):
            records.write_once(directory, self.docs(), self.guard)
        self.assertEqual(before, partial.read_bytes())
        self.assertEqual(1, len(list(directory.iterdir())))

    def test_short_write_is_retained_and_cannot_be_retried(self):
        directory = self.root / "record"
        real = os.write
        def short(fd, raw):
            return real(fd, raw[:3])
        with patch.object(records.os, "write", side_effect=short), self.assertRaisesRegex(
                ValueError, "SHORT_WRITE"):
            records.write_once(directory, self.docs(), self.guard)
        self.assertEqual(b'{"d', (directory / records.DOCUMENT_NAMES[0]).read_bytes())
        self.assertFalse((directory / records.SEAL_NAME).exists())
        with self.assertRaisesRegex(ValueError, "PARTIAL_RETAINED"):
            records.write_once(directory, self.docs(), self.guard)

    def test_fsync_failure_before_seal_retains_partial_output(self):
        directory = self.root / "record"
        real, calls = os.fsync, 0
        def failed(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError(errno.EIO, "fsync failure")
            return real(fd)
        with patch.object(records.os, "fsync", side_effect=failed), self.assertRaises(OSError):
            records.write_once(directory, self.docs(), self.guard)
        self.assertTrue((directory / records.DOCUMENT_NAMES[0]).exists())
        self.assertFalse((directory / records.SEAL_NAME).exists())

    def test_fsync_at_seal_failure_never_returns_new_execution_permission(self):
        directory = self.root / "record"
        real = os.fsync
        def failed(fd):
            seal = directory / records.SEAL_NAME
            if seal.exists() and os.fstat(fd).st_ino == seal.stat().st_ino:
                raise OSError(errno.EIO, "seal fsync failure")
            return real(fd)
        with patch.object(records.os, "fsync", side_effect=failed), self.assertRaises(OSError):
            records.write_once(directory, self.docs(), self.guard)
        self.assertEqual(set(records.LIMITS), {p.name for p in directory.iterdir()})
        # Bytes may have survived the failing fsync. They never authorize replay.
        replay = records.verify_sealed(directory, self.docs(), self.guard)
        self.assertTrue(replay["replay"])
        self.assertFalse(replay["allow_run"])

    def test_concurrent_extra_member_after_create_blocks_without_cleanup(self):
        directory = self.root / "record"
        inserted = False
        def raced():
            nonlocal inserted
            if not inserted and (directory / records.DOCUMENT_NAMES[0]).exists():
                inserted = True
                extra = directory / "unexpected.json"
                extra.write_bytes(b"{}")
                extra.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "RECORD_MEMBERS|METADATA_CHANGED"):
            records.write_once(directory, self.docs(), raced)
        self.assertTrue((directory / "unexpected.json").exists())
        self.assertFalse((directory / records.SEAL_NAME).exists())

    def test_deadline_after_first_file_retains_no_seal(self):
        directory = self.root / "record"
        def expired():
            if (directory / records.DOCUMENT_NAMES[0]).exists():
                raise ValueError("WINDOW_EXPIRED")
        with self.assertRaisesRegex(ValueError, "WINDOW_EXPIRED"):
            records.write_once(directory, self.docs(), expired)
        self.assertTrue(directory.exists())
        self.assertFalse((directory / records.SEAL_NAME).exists())

    def test_unknown_file_duplicate_json_and_file_size_rejected_before_mkdir(self):
        for changes in ({"unknown.json": b"{}"},
                        {records.DOCUMENT_NAMES[0]: b'{"x":1,"x":2}'},
                        {records.DOCUMENT_NAMES[0]: b" " * (256 * 1024 + 1)}):
            docs = dict(self.docs(), **changes)
            with self.assertRaises(ValueError):
                records.write_once(self.root / "record", docs, self.guard)
            self.assertFalse((self.root / "record").exists())

    def test_actual_allocation_budget_rejects_and_retains_created_directory(self):
        directory = self.root / "record"
        with patch.object(records, "INODE_LIMIT", 5), self.assertRaisesRegex(ValueError, "RECORD_BUDGET"):
            records.write_once(directory, self.docs(), self.guard)
        self.assertFalse(directory.exists())
        original = records._allocation
        def allocation(held, opened, guard):
            result = original(held, opened, guard)
            if opened:
                raise ValueError("RECONCILIATION_RECORD_BUDGET")
            return result
        with patch.object(records, "_allocation", side_effect=allocation), self.assertRaisesRegex(
                ValueError, "RECORD_BUDGET"):
            records.write_once(directory, self.docs(), self.guard)
        self.assertTrue(directory.exists())
        self.assertFalse((directory / records.SEAL_NAME).exists())


if __name__ == "__main__":
    unittest.main()
