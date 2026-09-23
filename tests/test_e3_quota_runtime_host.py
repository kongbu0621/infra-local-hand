"""Q1 host proof rejection tests; no systemd, quota or privileged fixture.

Directory FDs, no-follow opens and cgroup.events reads use real temporary files.
Their ownership checks and all proc/mount/namespace observations are explicitly
LOGIC_ONLY substitutions. An empty synthetic file tree is not a live cgroup
proof, host acceptance or permission to run the Q1 query.
"""
from contextlib import ExitStack
from dataclasses import replace
import errno
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import admission as a, protected_inputs as p, systemd_runtime as r
    from test_e3_quota_monitor import binding, decode, fixture
    from test_e3_quota_worker import runtime


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux host proof logic only")
class HostProofTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.parent = self.directory / "parent"
        self.parent.mkdir()
        self.events = self.parent / "cgroup.events"
        self.events.write_bytes(b"populated 0\nfrozen 0\n")
        metadata = self.parent.stat()
        self.config = replace(runtime(), cgroup_parent_device=metadata.st_dev,
                              cgroup_parent_inode=metadata.st_ino)
        value = fixture()
        value["cgroup_parent"] = "/" + self.config.query_slice
        self.bound = binding(decode(value))
        self.controller = r.Q1Controller.__new__(r.Q1Controller)
        self.controller.config = self.config
        self.controller.manifest = self.bound.manifest
        self.controller.config_path = "/synthetic/admin/runtime.json"
        self.controller.journal = Mock(control_dir="/synthetic/control")
        self.fdinfo = b"pos:\t0\nmnt_id:\t4242\n"
        self.device = f"{os.major(metadata.st_dev)}:{os.minor(metadata.st_dev)}"
        self.mountinfo = self.mount_record()
        self.open_count = 0
        self.replace_on_reopen = False
        # Preserve the actual component-wise NOFOLLOW opens; only the fixture's
        # ownership policy and mapping from the fixed cgroup path are synthetic.
        self.stack.enter_context(patch.object(p, "_protected"))
        self.stack.enter_context(patch.object(r, "open_protected", side_effect=self.open_parent))
        self.stack.enter_context(patch.object(r, "_fixed_read", side_effect=self.proc_read))

    def mount_record(self, *, mount_id="4242", filesystem="cgroup2", device=None):
        return (f"{mount_id} 1 {device or self.device} / /sys/fs/cgroup rw - "
                f"{filesystem} cgroup rw\n").encode()

    def proc_read(self, filename, maximum=65536):
        if filename.startswith("/proc/self/fdinfo/"):
            return self.fdinfo
        if filename == "/proc/self/mountinfo":
            return self.mountinfo
        if filename == "/proc/1/comm":
            return b"systemd\n"
        raise AssertionError(f"unexpected host read: {filename}")

    def open_parent(self, filename, *, directory=False):
        self.assertEqual(filename, "/sys/fs/cgroup" + self.bound.manifest.cgroup_parent)
        self.assertTrue(directory)
        self.open_count += 1
        if self.replace_on_reopen and self.open_count == 2:
            self.parent.rename(self.directory / "original")
            self.parent.mkdir()
            (self.parent / "cgroup.events").write_bytes(b"populated 0\n")
        return p.open_protected(str(self.parent), directory=True)

    def test_bound_parent_requires_explicit_empty_population(self):
        self.assertTrue(self.controller._parent_empty(self.bound))
        self.events.write_bytes(b"populated 1\nfrozen 0\n")
        self.assertFalse(self.controller._parent_empty(self.bound))

    def test_missing_duplicate_invalid_or_oversized_population_is_not_empty(self):
        cases = (b"", b"frozen 0\n", b"populated 0\npopulated 1\n", b"populated 2\n",
                 b"populated\n", b"populated 0 extra\n", b"populated 0\n" + b"x" * 4096)
        for content in cases:
            with self.subTest(content=content[:50]):
                self.events.write_bytes(content)
                with self.assertRaises(a.Rejected):
                    self.controller._parent_empty(self.bound)

    def test_missing_symlink_and_fifo_events_never_become_empty_proof(self):
        self.events.unlink()
        with self.assertRaises(FileNotFoundError):
            self.controller._parent_empty(self.bound)
        target = self.directory / "pretend-events"
        target.write_bytes(b"populated 0\n")
        self.events.symlink_to(target)
        with self.assertRaises(OSError):
            self.controller._parent_empty(self.bound)
        self.events.unlink()
        os.mkfifo(self.events, 0o600)
        with self.assertRaisesRegex(a.Rejected, "CGROUP_EVENTS_TYPE"):
            self.controller._parent_empty(self.bound)

    def test_fd_mount_identity_must_uniquely_match_bound_device_and_cgroup2(self):
        cases = (
            (b"pos: 0\n", self.mount_record()),
            (b"mnt_id: 4242\nmnt_id: 4242\n", self.mount_record()),
            (b"mnt_id: unknown\n", self.mount_record()),
            (self.fdinfo, self.mount_record(mount_id="4243")),
            (self.fdinfo, self.mount_record(filesystem="tmpfs")),
            (self.fdinfo, self.mount_record(device="999:999")),
            (self.fdinfo, self.mount_record() + self.mount_record()),
        )
        for fdinfo, mountinfo in cases:
            with self.subTest(fdinfo=fdinfo, mountinfo=mountinfo):
                self.fdinfo, self.mountinfo = fdinfo, mountinfo
                with self.assertRaises(a.Rejected):
                    self.controller._parent_empty(self.bound)

    def test_parent_identity_mismatch_and_replacement_cannot_prove_empty(self):
        self.controller.config = replace(self.config, cgroup_parent_inode=self.config.cgroup_parent_inode + 1)
        with self.assertRaisesRegex(a.Rejected, "CGROUP_PARENT_CHANGED"):
            self.controller._parent_empty(self.bound)
        self.controller.config = self.config
        self.open_count = 0
        self.replace_on_reopen = True
        with self.assertRaisesRegex(a.Rejected, "CGROUP_PARENT_CHANGED"):
            self.controller._parent_empty(self.bound)
        self.assertEqual(self.open_count, 2)

    def test_event_read_failure_is_retained_instead_of_becoming_empty(self):
        with patch.object(r, "read_fd", side_effect=OSError(errno.EIO, "synthetic events read failure")):
            with self.assertRaises(OSError) as failure:
                self.controller._parent_empty(self.bound)
        self.assertEqual(failure.exception.errno, errno.EIO)

    def host_patches(self, *, boot=None, namespaces=None, own_cgroup="/controller.slice"):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(r.os, "getuid", return_value=0))
        stack.enter_context(patch.object(r.os, "geteuid", return_value=0))
        stack.enter_context(patch.object(r, "_boot_id", return_value=boot or self.bound.manifest.boot_id))
        expected = SimpleNamespace(st_dev=self.config.initial_userns_device,
                                   st_ino=self.config.initial_userns_inode)
        stack.enter_context(patch.object(r.os, "stat", side_effect=namespaces or [expected, expected]))
        stack.enter_context(patch.object(r, "_own_cgroup", return_value=own_cgroup))
        installation = stack.enter_context(patch.object(r, "verify_installation"))
        return stack, installation

    def test_host_admission_rejects_changed_boot_or_either_user_namespace(self):
        expected = SimpleNamespace(st_dev=self.config.initial_userns_device,
                                   st_ino=self.config.initial_userns_inode)
        wrong = SimpleNamespace(st_dev=expected.st_dev, st_ino=expected.st_ino + 1)
        cases = (
            ({"boot": "different-boot"}, "BOOT_CHANGED"),
            ({"namespaces": [wrong, expected]}, "USERNS_CHANGED"),
            ({"namespaces": [expected, wrong]}, "USERNS_CHANGED"),
        )
        for arguments, reason in cases:
            with self.subTest(reason=reason, arguments=arguments):
                stack, installation = self.host_patches(**arguments)
                with stack, self.assertRaisesRegex(a.Rejected, reason):
                    self.controller._admit_host(self.bound)
                installation.assert_not_called()
        self.controller.journal.verify_directory.assert_not_called()

    def test_controller_in_query_parent_or_descendant_is_refused_before_proof(self):
        parent = self.bound.manifest.cgroup_parent
        for own in (parent, parent + "/controller.service"):
            with self.subTest(own=own):
                stack, installation = self.host_patches(own_cgroup=own)
                with stack, self.assertRaisesRegex(a.Rejected, "CONTROLLER_IN_QUERY_TREE"):
                    self.controller._admit_host(self.bound)
                installation.assert_not_called()
        self.controller.journal.verify_directory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
