"""Archive read output isolation across Linux mount views and real CLI use."""
from contextlib import ExitStack, redirect_stdout
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import test_local_hand_artifact_archive as fixtures
from local_hand_jobs import artifact_archive as consumer
from local_hand_jobs import archive_read_paths as paths


@unittest.skipUnless(sys.platform == "linux", "Linux mountinfo and directory descriptors")
class ReadPathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.parent = self.root / "output-parent"
        self.source.mkdir(mode=0o700)
        self.parent.mkdir(mode=0o700)
        self.source_fd = os.open(self.source, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, self.source_fd)
        self.parent_fd = os.open(self.parent, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, self.parent_fd)
        self.source_info = os.fstat(self.source_fd)
        self.parent_info = os.fstat(self.parent_fd)
        self.identity = self.parent_info.st_dev, self.parent_info.st_ino
        self.device = os.major(self.source_info.st_dev), os.minor(self.source_info.st_dev)

    def mount(self, root="/", point="/", device=None):
        return dict(root=Path(root), point=Path(point), device=device or self.device)

    def check(self):
        paths.assert_output_outside_store(self.source, self.source_fd, self.parent, self.parent_fd)

    def model(self, records, *, parent_id=2, identities=None):
        """Model static mount views; actual FD identities remain independently held."""
        stack = ExitStack()
        stack.enter_context(mock.patch.object(paths, "_mounts", return_value=records))
        stack.enter_context(mock.patch.object(paths, "_mount_id",
            side_effect=lambda fd: 1 if fd == self.source_fd else parent_id))
        if identities is not None:
            stack.enter_context(mock.patch.object(paths, "_projected_identity",
                side_effect=lambda fd, parts: identities[tuple(parts)]))
        return stack

    def assert_rejected(self, code):
        with self.assertRaises(consumer.ArchiveError) as caught:
            self.check()
        self.assertEqual(caught.exception.code, code)

    def test_real_independent_directories_are_allowed(self):
        self.check()

    def test_double_slash_roots_allow_independent_paths_and_reject_aliases(self):
        source, parent = self.source, self.parent
        records = {1: self.mount(), 2: self.mount(source / "nested", parent)}
        try:
            for double_source, double_parent in ((True, False), (False, True), (True, True)):
                with self.subTest(source=double_source, parent=double_parent):
                    self.source = Path("/" + str(source)) if double_source else source
                    self.parent = Path("/" + str(parent)) if double_parent else parent
                    self.check()
                    with self.model(records, identities={("nested",): self.identity}):
                        self.assert_rejected("INVALID_INPUT")
        finally:
            self.source, self.parent = source, parent

    def test_same_directory_descriptor_is_rejected_even_under_another_name(self):
        self.parent_fd, original_fd = self.source_fd, self.parent_fd
        try:
            with self.model({1: self.mount()}, parent_id=1):
                self.assert_rejected("INVALID_INPUT")
        finally:
            self.parent_fd = original_fd

    def test_root_and_descendant_mount_aliases_are_rejected(self):
        for suffix in ((), ("retained",), ("retained", "child")):
            with self.subTest(suffix=suffix):
                position = self.source.joinpath(*suffix)
                records = {1: self.mount(), 2: self.mount(position, self.parent)}
                with self.model(records, identities={suffix: self.identity}):
                    self.assert_rejected("INVALID_INPUT")

    def test_unrelated_same_filesystem_output_is_allowed(self):
        with self.model({1: self.mount(), 2: self.mount(self.parent, self.parent)}), \
                mock.patch.object(paths, "_projected_identity", side_effect=AssertionError("no input projection")):
            self.check()

    def test_visible_child_mount_on_different_device_is_rejected(self):
        child_device = (42, 7)
        parent_info = SimpleNamespace(st_dev=os.makedev(*child_device), st_ino=self.parent_info.st_ino)
        identity = parent_info.st_dev, parent_info.st_ino
        records = {1: self.mount(), 2: self.mount("/payload/nested", self.parent, child_device),
                   3: self.mount("/payload", self.source / "child-mount", child_device)}
        fstat = os.fstat
        with self.model(records, identities={("child-mount", "nested"): identity}), \
                mock.patch.object(paths.os, "fstat", side_effect=lambda fd:
                    parent_info if fd == self.parent_fd else fstat(fd)):
            self.assert_rejected("INVALID_INPUT")

    def test_hidden_missing_or_different_object_does_not_imply_alias(self):
        records = {1: self.mount(), 2: self.mount(self.source / "hidden", self.parent)}
        for visible in (None, (self.identity[0], self.identity[1] + 1)):
            with self.subTest(visible=visible), self.model(records, identities={("hidden",): visible}):
                self.check()

    def test_hidden_view_does_not_mask_another_visible_alias(self):
        records = {1: self.mount(), 2: self.mount(self.source / "hidden", self.parent),
                   3: self.mount(self.source / "hidden", self.source / "visible")}
        identities = {("hidden",): None, ("visible",): self.identity}
        with self.model(records, identities=identities):
            self.assert_rejected("INVALID_INPUT")

    def test_projection_io_failure_is_uncertain_not_safe(self):
        records = {1: self.mount(), 2: self.mount(self.source / "hidden", self.parent)}
        for failure in (PermissionError(errno.EACCES, "denied"), OSError(errno.EIO, "unreadable")):
            with self.subTest(errno=failure.errno), self.model(records), \
                    mock.patch.object(paths, "_projected_identity", side_effect=failure):
                self.assert_rejected("IO_UNCERTAIN")

    def test_missing_mismatched_or_changed_descriptor_binding_is_uncertain(self):
        with self.model({1: self.mount()}):
            self.assert_rejected("IO_UNCERTAIN")
        with self.model({1: self.mount(), 2: self.mount(device=(42, 7))}):
            self.assert_rejected("IO_UNCERTAIN")
        with mock.patch.object(paths, "_mounts", return_value={1: self.mount(), 2: self.mount()}), \
                mock.patch.object(paths, "_mount_id", side_effect=[1, 2, 1, 3]):
            self.assert_rejected("IO_UNCERTAIN")

    def test_projected_identity_accepts_proven_missing_or_regular_file_views(self):
        child = self.source / "可见 子目录"
        child.mkdir(mode=0o777)
        child.chmod(0o777)  # Observing another object is not permission to write it.
        info = child.stat()
        self.assertEqual(paths._projected_identity(self.source_fd, (child.name,)),
                         (info.st_dev, info.st_ino))
        self.assertIsNone(paths._projected_identity(self.source_fd, ("absent",)))
        (self.source / "link").symlink_to(child, target_is_directory=True)
        (self.source / "file").write_text("not a directory")
        self.assertIsNone(paths._projected_identity(self.source_fd, ("file",)))
        self.assertIsNone(paths._projected_identity(self.source_fd, ("file", "hidden-child")))
        with self.assertRaises(OSError):
            paths._projected_identity(self.source_fd, ("link",))
        # The caller's held FD survives success and every rejected projection.
        self.assertEqual(os.fstat(self.source_fd).st_ino, self.source_info.st_ino)

    def test_unobservable_non_directory_type_is_not_proof_of_separation(self):
        (self.source / "file").write_text("visible regular file")
        for error_number in (errno.EACCES, errno.EIO):
            with self.subTest(errno=error_number), \
                    mock.patch.object(paths.os, "stat", side_effect=OSError(error_number, "unobservable")) as stat:
                with self.assertRaises(OSError) as caught:
                    paths._projected_identity(self.source_fd, ("file", "hidden-child"))
                self.assertEqual(caught.exception.errno, error_number)
                self.assertEqual(stat.call_args.kwargs["follow_symlinks"], False)
        self.assertEqual(os.fstat(self.source_fd).st_ino, self.source_info.st_ino)

    def test_proc_reads_are_bounded_even_for_zero_reported_size(self):
        for limit in (paths.MAX_FDINFO, paths.MAX_MOUNTINFO):
            with self.subTest(limit=limit):
                stream = io.BytesIO(b"x" * (limit + 2))
                with mock.patch("builtins.open", return_value=stream), \
                        mock.patch.object(stream, "read", wraps=stream.read) as read:
                    with self.assertRaises(consumer.ArchiveError) as caught:
                        paths._read_proc("/proc/self/mountinfo", limit)
                    self.assertEqual(caught.exception.code, "IO_UNCERTAIN")
                    read.assert_called_once_with(limit + 1)

    def test_malformed_empty_duplicate_mount_metadata_is_uncertain(self):
        valid = "1 0 8:1 / / rw - ext4 /dev/test rw\n"
        for raw in ("", "garbage\n", valid + valid, valid.replace("8:1", "bad"),
                    valid.replace("8:1", "9" * 5000 + ":1"),
                    valid.replace("/ / rw", "/ relative rw"), valid.replace("/ / rw", "/../bad / rw")):
            with self.subTest(raw=raw), mock.patch.object(paths, "_read_proc", return_value=raw):
                with self.assertRaises(consumer.ArchiveError) as caught:
                    paths._mounts()
                self.assertEqual(caught.exception.code, "IO_UNCERTAIN")

    def test_unicode_whitespace_and_kernel_escaped_mount_paths_are_preserved(self):
        raw = "9 0 8:1 /根\\040目录 /挂载\u00a0名字\u2028后\\011缀\\134 rw - ext4 /dev/test rw\n"
        with mock.patch.object(paths, "_read_proc", return_value=raw):
            records = paths._mounts()
        self.assertEqual(records[9]["root"], Path("/根 目录"))
        self.assertEqual(records[9]["point"], Path("/挂载\u00a0名字\u2028后\t缀\\"))

    def test_invalid_fdinfo_is_uncertain(self):
        for raw in ("", "mnt_id: 3\nmnt_id: 3\n", "mnt_id: none\n", "mnt_id: -1\n"):
            with self.subTest(raw=raw), mock.patch.object(paths, "_read_proc", return_value=raw):
                with self.assertRaises(consumer.ArchiveError) as caught:
                    paths._mount_id(self.source_fd)
                self.assertEqual(caught.exception.code, "IO_UNCERTAIN")


@unittest.skipUnless(sys.platform == "linux" and fixtures.HAS_LEDGER,
                     "Linux and installed Ledger required")
class ArchiveReadPathIntegrationTests(fixtures.BundleFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.store = self.root / "归档 空格\u2028后"
        status = dict(operation_id=fixtures.OP, request_digest="a" * 64,
            lifecycle="TERMINAL", phase="EXITED", outcome="SUCCEEDED", evidence="SEALED",
            observed_at=1.5, seal_refs=[{key: self.descriptor[key] for key in ("seal_id", "seal_sha256")}])
        status_path = self.root / "status.json"
        status_path.write_bytes(consumer._json(status))
        self.archived = consumer.archive_result(self.store, producer="test:read-boundaries",
            status_path=status_path, status_sha256=consumer._sha(status_path.read_bytes()),
            evidence_dir=self.evidence)
        self.output = self.root / "输出\t 名字\u00a0后"

    def tree(self):
        return {str(p.relative_to(self.store)): p.read_bytes() for p in self.store.rglob("*") if p.is_file()}

    def read(self):
        return consumer.read_version(self.store, artifact_id=self.archived["artifact_id"],
                                     version_id=self.archived["version_id"], output=self.output)

    def cli(self):
        response = io.StringIO()
        arguments = ["read", "--store", str(self.store), "--artifact-id", self.archived["artifact_id"],
                     "--version-id", self.archived["version_id"], "--output", str(self.output)]
        with redirect_stdout(response):
            code = consumer.main(arguments)
        return code, json.loads(response.getvalue())

    def test_projection_close_failure_is_read_uncertainty_and_can_continue(self):
        hidden = self.store / "hidden"
        hidden.mkdir(mode=0o700)
        parent = self.root / "independent-parent"
        parent.mkdir(mode=0o700)
        self.output = parent / "readback"
        device = self.store.stat().st_dev
        records = {
            1: dict(device=(os.major(device), os.minor(device)), root=Path("/"), point=Path("/")),
            2: dict(device=(os.major(device), os.minor(device)), root=hidden, point=parent),
        }
        duplicate, close = os.dup, os.close
        observed = dict(fd=None, calls=0, injected=False)
        def duplicate_projection(fd):
            result = duplicate(fd)
            observed["fd"] = result
            return result
        def fail_close_after_release(fd):
            if fd == observed["fd"]:
                observed["calls"] += 1
                if not observed["injected"]:
                    close(fd)
                    observed["injected"] = True
                    raise OSError(errno.EIO, "close failed after releasing the descriptor")
            return close(fd)
        def mount_id(fd):
            return 1 if Path(os.readlink(f"/proc/self/fd/{fd}")) == self.store else 2
        before = self.tree()
        descriptors = set(os.listdir("/proc/self/fd"))
        with mock.patch.object(paths, "_mounts", return_value=records), \
                mock.patch.object(paths, "_mount_id", side_effect=mount_id), \
                mock.patch.object(paths.os, "dup", side_effect=duplicate_projection), \
                mock.patch.object(paths.os, "close", side_effect=fail_close_after_release):
            code, response = self.cli()
        self.assertEqual(code, 1)
        self.assertEqual(response["code"], "IO_UNCERTAIN")
        self.assertTrue(observed["injected"])
        self.assertEqual(observed["calls"], 1)
        self.assertEqual(set(os.listdir("/proc/self/fd")), descriptors)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.tree(), before)
        self.assertEqual(self.read()["status"], "READ")
        self.assertEqual(self.tree(), before)
        self.assertEqual(response["commit_state"], "not_applicable")

    def test_failure_after_output_publication_does_not_claim_an_archive_commit(self):
        before = self.tree()
        publish = consumer._publish_files
        def published_then_failed(*args, **kwargs):
            publish(*args, **kwargs)
            raise OSError(errno.EIO, "late output completion failure")
        with mock.patch.object(consumer, "_publish_files", side_effect=published_then_failed):
            code, response = self.cli()
        self.assertEqual(code, 1)
        retained = {p.name: p.read_bytes() for p in self.output.iterdir()}
        self.assertEqual(set(retained), set(consumer.LIMITS))
        for name, raw in self.raw.items():
            self.assertEqual(retained[name], raw)
        self.assertEqual(self.tree(), before)
        self.output = self.root / "later-read"
        self.assertEqual(self.read()["status"], "READ")
        self.assertEqual(self.tree(), before)
        self.assertEqual(response["commit_state"], "not_applicable")
        self.assertNotIn("reconcile the original request", response["message"])

    def test_existing_read_output_is_preserved_without_unknown_commit_state(self):
        self.read()
        before = self.tree()
        retained = {p.name: p.read_bytes() for p in self.output.iterdir()}
        code, response = self.cli()
        self.assertEqual(code, 1)
        self.assertEqual({p.name: p.read_bytes() for p in self.output.iterdir()}, retained)
        self.assertEqual(self.tree(), before)
        self.output = self.root / "another-read"
        self.assertEqual(self.read()["status"], "READ")
        self.assertEqual(response["commit_state"], "not_applicable")
        self.assertNotIn("reconcile the original request", response["message"])

    def test_real_cli_reads_exact_evidence_without_changing_store(self):
        before = self.tree()
        script = ("import sys; sys.path.insert(0, sys.argv.pop(1)); "
                  "from local_hand_jobs.artifact_archive import main; raise SystemExit(main())")
        completed = subprocess.run([sys.executable, "-I", "-B", "-c", script,
            str(Path(consumer.__file__).parents[1]), "read", "--store", str(self.store),
            "--artifact-id", self.archived["artifact_id"], "--version-id", self.archived["version_id"],
            "--output", str(self.output)], capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "READ")
        self.assertTrue(result["content_verified"])
        for name, expected in result["files"].items():
            raw = (self.output / name).read_bytes()
            self.assertEqual(len(raw), expected["size"])
            self.assertEqual(consumer._sha(raw), expected["sha256"])
        self.assertEqual(self.tree(), before)

    def test_uncertain_mount_metadata_does_not_publish_and_allows_later_read(self):
        before = self.tree()
        with mock.patch.object(paths, "_read_proc", side_effect=OSError(errno.EIO, "metadata unavailable")), \
                mock.patch.object(consumer, "_publish_files", side_effect=AssertionError("must not publish")):
            with self.assertRaises(consumer.ArchiveError) as caught:
                self.read()
        self.assertEqual(caught.exception.code, "IO_UNCERTAIN")
        self.assertFalse(self.output.exists())
        self.assertEqual(self.tree(), before)
        self.assertEqual(self.read()["status"], "READ")
        self.assertEqual(self.tree(), before)

    def test_mount_alias_refusal_prevents_any_output_and_preserves_recovery_checkpoint(self):
        before = self.tree()
        checkpoint = consumer.recovery_checkpoint(self.store)
        with mock.patch.object(paths, "assert_output_outside_store",
                side_effect=consumer.ArchiveError("INVALID_INPUT", "output aliases input archive")) as guard, \
                mock.patch.object(consumer, "_publish_files", side_effect=AssertionError("must not publish")):
            with self.assertRaises(consumer.ArchiveError) as caught:
                self.read()
        self.assertEqual(caught.exception.code, "INVALID_INPUT")
        guard.assert_called_once()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.tree(), before)
        self.assertEqual(consumer.recovery_checkpoint(self.store), checkpoint)


class ReadOnlyFailureCLITests(unittest.TestCase):
    def test_checkpoint_io_failure_has_no_archive_commit_to_reconcile(self):
        captured = io.StringIO()
        with mock.patch.object(consumer, "recovery_checkpoint", side_effect=OSError(errno.EIO, "read failed")), \
                redirect_stdout(captured):
            code = consumer.main(["recovery-checkpoint", "--store", "unused"])
        response = json.loads(captured.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(response["commit_state"], "not_applicable")
        self.assertNotIn("reconcile the original request", response["message"])


if __name__ == "__main__":
    unittest.main()
