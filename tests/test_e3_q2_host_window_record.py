"""Real local syscalls, with explicit synthetic readiness/FS qualification.

No test here establishes ext4 durability on the Work overlay filesystem, field
readiness, remote termination, guest execution or Q2 acceptance.
"""
import copy
import errno
import multiprocessing
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux fcntl/ext4 and protected-fd record implementation", allow_module_level=True)

from e3_host import q2_host_window_billing as billing
from e3_host import q2_host_window_contract as c
from e3_host import q2_host_window_record as r
from e3_host import q2_reconciliation_delivery as delivery
from e3_host import q2_reconciliation_io as io


def binding(location):
    return c.make_binding(implementation_commit="a"*40, source_tree="b"*40,
        source_files_sha256="c"*64, attempt_id="model-only-20260927",
        plan_sha256="d"*64, amendment_sha256="e"*64, configuration_sha256="f"*64,
        wrapper_sha256="1"*64, location=location)


def qualified_model(parent, guard):
    """Qualification is a model; all metadata/reads/writes/fsyncs remain real."""
    guard()
    info = os.fstat(parent.fd)
    return dict(schema=r.FILESYSTEM_SCHEMA, device=info.st_dev, mount_id=1,
        mountpoint="/", source="/dev/synthetic-only", mountinfo_sha256="1"*64,
        superblock_sha256="2"*64, block_size=4096, cluster_size=4096,
        parent_flags=r.FS_EXTENTS_FL, parent_size=info.st_size,
        available_bytes=1024**3, free_inodes=100000, allocation_bound=65536,
        logical_bound=16384, inode_bound=4)


@unittest.skipUnless(sys.platform.startswith("linux") and os.geteuid() == 0,
    "Linux root protected temporary files")
class HostWindowRecords(unittest.TestCase):
    def setUp(self):
        home = Path.home()
        if any(os.stat(path).st_mode & 0o022 for path in (home, *home.parents)):
            self.skipTest("No protected temporary parent")
        self.tmp = tempfile.TemporaryDirectory(prefix="q2-host-window-test-", dir=home)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.history = self.root / "history"
        self.history.mkdir(mode=0o700)
        (self.history / "old").write_bytes(b"unchanged historical evidence")
        (self.history / "old").chmod(0o400)
        self.location = dict(schema=c.SOURCES_SCHEMA, parent=str(self.root),
            directory=str(self.root / c.DIRECTORY_NAME), expected_boot_id=r._boot(lambda:None),
            startup_closure=c.STARTUP_AUTHORITY["closure"], carrier_sha256=c.CARRIER_SHA256,
            carrier_bytes=c.CARRIER_BYTES, host_attestation_sha256=c.ATTESTATION_SHA256,
            host_attestation_bytes=c.ATTESTATION_BYTES)
        self.binding = binding(self.location)
        self.window = delivery.Window()
        self.bill = self.make_bill()

    def make_bill(self):
        device = self.root.stat().st_dev
        declarations = []
        for identity, kind, relative, amount in (
            ("old", "historical", "history", dict(bytes=16384, inodes=8)),
            ("new-host-capture", "capture", "future-capture", dict(bytes=8*1024**2, inodes=64)),
            ("host-window-marker", "marker", c.DIRECTORY_NAME, dict(bytes=65536, inodes=4))):
            declarations.append(dict(id=identity, kind=kind, category="capture", commitment=amount,
                covered_paths=[str(self.root / relative)], devices=[device], evidence_sha256="3"*64))
        inventory = dict(host_id=c.ATTESTATION_SHA256, guest_id="4"*64,
            scans={str(self.history):io.snapshot(self.history, self.window.guard)},
            expected_roots={str(self.history):"capture"},
            devices=[dict(device=device, available_bytes=1024**3, free_inodes=100000)],
            obligations=declarations, marker=dict(path=self.location["directory"], device=device, state="ABSENT"),
            early_audit=dict(evidence_sha256="5"*64, host_obligation_ids=[],
                guest_obligation_id="new-owner-pool", guest_reserved=dict(bytes=65536, inodes=4)),
            coverage_sha256="6"*64)
        return billing.quote_host(inventory)

    def precheck(self):
        held = r.precheck(self.location, self.binding, self.window, self.bill)
        self.addCleanup(held.close)
        return held

    def modeled(self):
        self.addCleanup(patch.stopall)
        patch.object(r.c, "require_field_readiness", return_value=None).start()
        patch.object(r, "filesystem", side_effect=qualified_model).start()

    def consume(self):
        record = self.precheck().consume()
        self.addCleanup(record.close)
        return record

    def test_production_gate_before_any_live_open_or_mkdir(self):
        with patch.object(r.os, "open", side_effect=AssertionError("field read")), \
             patch.object(r.os, "mkdir", side_effect=AssertionError("field write")), \
             self.assertRaisesRegex(ValueError, "FIELD_READINESS_UNPROVEN"):
            self.precheck()

    def test_real_environment_qualification_fails_without_trial_writes(self):
        # This is not the model path: actual Work mounts are overlay+volatile.
        with io.HeldPath(str(self.root), self.window.guard, directory=True, allowed_uids={0}) as parent:
            with patch.object(r.os, "mkdir", side_effect=AssertionError("trial write")):
                try:
                    value = r.filesystem(parent, self.window.guard)
                except (OSError, ValueError) as error:
                    self.assertTrue(str(error))
                else:
                    self.assertEqual(r.FILESYSTEM_SCHEMA, value["schema"])

    def test_modeled_success_real_files_fsync_readback_and_noatime(self):
        self.modeled()
        old_before = io.metadata((self.history / "old").stat())
        origin = self.window.fields()
        real_sync = os.fsync
        calls = []
        def synced(fd):
            calls.append((os.fstat(fd).st_ino, stat.S_ISDIR(os.fstat(fd).st_mode)))
            return real_sync(fd)
        with patch.object(r.os, "fsync", side_effect=synced):
            held = self.consume()
        self.assertGreaterEqual(len(calls), 5)
        self.assertTrue(any(not is_directory for _, is_directory in calls))
        self.assertEqual(origin, c.document(held.intent_raw)["window"])
        self.assertEqual([c.INTENT_NAME], sorted(os.listdir(held.directory_fd)))
        file = Path(self.location["directory"]) / c.INTENT_NAME
        before = io.metadata(file.stat())
        held.verify(); held.verify()
        self.assertEqual(before, io.metadata(file.stat()))
        self.assertEqual(old_before, io.metadata((self.history / "old").stat()))
        self.assertEqual(0o400, stat.S_IMODE(file.stat().st_mode))
        self.assertEqual(sum(row["source_metadata"]["size"] for row in held.snapshot["entries"]),
            held.evidence["actual"]["logical_bytes"])
        self.assertFalse(held.evidence["allow_run"])

    def test_same_complete_record_blocks_new_precheck_and_is_only_readonly(self):
        self.modeled(); held = self.consume()
        with self.assertRaisesRegex(ValueError, "ALREADY_CONSUMED"):
            self.precheck()
        report = r.verify_existing(self.location, self.binding, self.window, held.intent_sha256)
        self.assertFalse(report["allow_run"])
        self.assertEqual("CONSUMED_READ_ONLY", report["status"])

    def test_all_existing_object_kinds_are_consumed(self):
        self.modeled()
        marker = Path(self.location["directory"])
        for kind in ("directory", "file", "symlink"):
            with self.subTest(kind=kind):
                if kind == "directory": marker.mkdir(mode=0o700)
                elif kind == "file": marker.write_bytes(b"partial")
                else: marker.symlink_to(self.history)
                with self.assertRaisesRegex(ValueError, "ALREADY_CONSUMED"):
                    self.precheck()
                if kind == "directory": marker.rmdir()
                else: marker.unlink()

    def test_post_mkdir_fsync_error_retains_partial_and_blocks_next_process(self):
        self.modeled(); pre = self.precheck()
        with patch.object(r.os, "fsync", side_effect=OSError(errno.EIO, "model fsync failure")), \
             self.assertRaises(OSError):
            pre.consume()
        marker = Path(self.location["directory"])
        self.assertTrue(marker.is_dir())
        self.assertEqual([], list(marker.iterdir()))
        with self.assertRaisesRegex(ValueError, "ALREADY_CONSUMED"):
            self.precheck()

    def test_short_write_retained_no_completion_or_retry(self):
        self.modeled(); pre = self.precheck()
        real_write = os.write
        with patch.object(r.os, "write", side_effect=lambda fd,data:real_write(fd,data[:9])), \
             self.assertRaisesRegex(ValueError, "SHORT_WRITE"):
            pre.consume()
        self.assertEqual(9, (Path(self.location["directory"]) / c.INTENT_NAME).stat().st_size)
        with self.assertRaisesRegex(ValueError, "ALREADY_CONSUMED"):
            self.precheck()

    def test_noatime_denial_never_falls_back_or_creates_marker(self):
        self.modeled(); original = os.open; calls=[]
        def denied(name, flags, *args, **kwargs):
            calls.append(flags)
            if name == self.root.name and flags & os.O_NOATIME:
                raise PermissionError(errno.EPERM, "noatime denied")
            return original(name, flags, *args, **kwargs)
        with patch.object(r.os, "open", side_effect=denied), self.assertRaises(PermissionError):
            self.precheck()
        self.assertTrue(all(flags & os.O_NOATIME for flags in calls if not flags & os.O_PATH))
        self.assertFalse(Path(self.location["directory"]).exists())

    def test_acl_unknown_or_present_blocks_before_creation(self):
        self.modeled()
        for effect in (b"untrusted ACL", OSError(errno.EOPNOTSUPP, "unknown ACL support")):
            with self.subTest(effect=repr(effect)), patch.object(r.os, "getxattr") as call:
                if isinstance(effect, Exception): call.side_effect=effect
                else: call.return_value=effect
                with self.assertRaisesRegex(ValueError, "ACL_"):
                    self.precheck()
        self.assertFalse(Path(self.location["directory"]).exists())

    def test_bound_window_change_and_expired_preparation_do_not_write(self):
        self.modeled(); pre = self.precheck()
        self.window.deadline_ns += 1
        with self.assertRaisesRegex(ValueError, "ORIGIN_CHANGED"):
            pre.consume()
        self.assertFalse(Path(self.location["directory"]).exists())

    def test_writer_identity_change_after_precheck_refuses_before_mkdir(self):
        self.modeled()
        pre = self.precheck()
        for getter in ("geteuid", "getegid"):
            with self.subTest(getter=getter), patch.object(r.os, getter, return_value=12345), \
                    patch.object(r.os, "mkdir", side_effect=AssertionError("write after identity change")), \
                    self.assertRaisesRegex(ValueError, "HOST_WINDOW_ROOT_REQUIRED"):
                pre.consume()
        self.assertFalse(Path(self.location["directory"]).exists())

    def test_writer_identity_change_after_mkdir_retains_partial_without_intent(self):
        self.modeled()
        pre = self.precheck()
        original = os.mkdir
        changed = [False]
        def mkdir_then_change(*args, **kwargs):
            result = original(*args, **kwargs)
            changed[0] = True
            return result
        with patch.object(r.os, "mkdir", side_effect=mkdir_then_change), \
                patch.object(r.os, "geteuid", side_effect=lambda:12345 if changed[0] else 0), \
                self.assertRaisesRegex(ValueError, "HOST_WINDOW_ROOT_REQUIRED"):
            pre.consume()
        marker = Path(self.location["directory"])
        self.assertTrue(marker.is_dir())
        self.assertEqual([], list(marker.iterdir()))
        with self.assertRaisesRegex(ValueError, "ALREADY_CONSUMED"):
            self.precheck()

    def test_retained_record_rechecks_writer_identity_before_reading(self):
        self.modeled()
        held = self.consume()
        with patch.object(r.os, "getegid", return_value=12345), \
                patch.object(r.os, "open", side_effect=AssertionError("read after identity change")), \
                self.assertRaisesRegex(ValueError, "HOST_WINDOW_ROOT_REQUIRED"):
            held.verify()

    def test_identity_change_after_intent_open_prevents_payload_write(self):
        self.modeled()
        pre = self.precheck()
        original = os.open
        changed = [False]
        def open_then_change(path, *args, **kwargs):
            fd = original(path, *args, **kwargs)
            if path == c.INTENT_NAME:
                changed[0] = True
            return fd
        with patch.object(r.os, "open", side_effect=open_then_change), \
                patch.object(r.os, "getegid", side_effect=lambda:12345 if changed[0] else 0), \
                patch.object(r.os, "write", side_effect=AssertionError("payload write after identity change")), \
                self.assertRaisesRegex(ValueError, "HOST_WINDOW_ROOT_REQUIRED"):
            pre.consume()
        intent = Path(self.location["directory"]) / c.INTENT_NAME
        self.assertTrue(intent.is_file())
        self.assertEqual(0, intent.stat().st_size)
        with self.assertRaisesRegex(ValueError, "ALREADY_CONSUMED"):
            self.precheck()

    def test_marker_verification_after_preparation_uses_original_300_seconds(self):
        self.modeled()
        now=[100*c.NS]
        self.window=delivery.Window(monotonic=lambda:now[0], boottime=lambda:now[0])
        held=self.consume()
        now[0] += 150*c.NS
        held.verify()
        self.assertEqual(400*c.NS, held.evidence["window"]["deadline_ns"])
        now[0] += 151*c.NS
        with self.assertRaises(ValueError): held.verify()

    def test_preparation_expires_after_fsync_keeps_marker_but_returns_no_receipt(self):
        self.modeled(); now=[100*c.NS]
        self.window=delivery.Window(monotonic=lambda:now[0], boottime=lambda:now[0])
        pre=self.precheck(); original=os.fsync
        def delayed(fd):
            result=original(fd); now[0]+=141*c.NS
            return result
        with patch.object(r.os,"fsync",side_effect=delayed),self.assertRaisesRegex(ValueError,"PREPARATION_EXPIRED"):
            pre.consume()
        self.assertTrue(Path(self.location["directory"]).exists())

    def test_real_same_bytes_replacement_and_extra_member_fail(self):
        self.modeled(); held=self.consume()
        marker=Path(self.location["directory"])
        substitute=self.root/"substitute"
        substitute.write_bytes(held.intent_raw); substitute.chmod(0o400)
        os.replace(substitute,marker/c.INTENT_NAME)
        with self.assertRaisesRegex(ValueError,"CHANGED|REPLACED"):
            held.verify()

    def test_permitted_sibling_creation_but_parent_substitution_refused(self):
        self.modeled(); held=self.consume()
        (self.root/"authorized-sibling").mkdir(mode=0o700)
        held.verify()
        moved=self.root.with_name(self.root.name+"-moved")
        self.root.rename(moved)
        try:
            self.root.mkdir(mode=0o700)
            with self.assertRaisesRegex(ValueError,"PARENT_CHANGED"):
                held.verify()
        finally:
            self.root.rmdir(); moved.rename(self.root)

    def test_directory_symlink_race_after_exclusive_mkdir_never_writes_target(self):
        self.modeled(); pre=self.precheck(); original=os.mkdir
        marker=Path(self.location["directory"])
        def raced(name,*args,**kwargs):
            result=original(name,*args,**kwargs)
            if name==c.DIRECTORY_NAME:
                marker.rename(self.root/"retained-partial")
                marker.symlink_to(self.history)
            return result
        with patch.object(r.os,"mkdir",side_effect=raced),self.assertRaises(OSError):
            pre.consume()
        self.assertFalse((self.history/c.INTENT_NAME).exists())
        self.assertTrue((self.root/"retained-partial").is_dir())

    def test_original_boot_mismatch_rejects_absent_marker(self):
        self.modeled()
        self.location["expected_boot_id"]="00000000-0000-0000-0000-000000000000"
        self.binding=binding(self.location)
        with self.assertRaisesRegex(ValueError,"BOOT_CHANGED"):
            self.precheck()
        self.assertFalse(Path(self.location["directory"]).exists())

    def test_real_process_competition_only_one_durable_receipt(self):
        self.modeled()
        ctx=multiprocessing.get_context("fork")
        ready=ctx.Barrier(2); result=ctx.Queue()
        def contender():
            item=None
            try:
                pre=r.precheck(self.location,self.binding,self.window,self.bill)
                ready.wait(timeout=10)
                try:
                    item=pre.consume()
                    result.put((True,item.intent_sha256))
                finally: pre.close()
            except BaseException as error:
                result.put((False,type(error).__name__+":"+str(error)))
            finally:
                if item is not None:item.close()
        processes=[ctx.Process(target=contender) for _ in range(2)]
        for process in processes:process.start()
        for process in processes:
            process.join(timeout=15)
            if process.is_alive():process.kill();process.join()
            self.assertEqual(0,process.exitcode)
        outcomes=[result.get(timeout=3) for _ in processes]
        self.assertEqual(1,sum(success for success,_ in outcomes),outcomes)
        self.assertTrue((Path(self.location["directory"])/c.INTENT_NAME).is_file())


class HostWindowExt4Geometry(unittest.TestCase):
    def superblock(self):
        raw=bytearray(1024)
        struct.pack_into("<H",raw,56,0xEF53)
        struct.pack_into("<II",raw,24,2,2)
        struct.pack_into("<III",raw,92,0x4,0x42,0)
        return raw

    def test_non_bigalloc_exact_geometry_only(self):
        self.assertEqual((4096,4096),r._geometry(bytes(self.superblock())))
        for offset,value in ((24,3),(28,3),(100,0x200),(96,0x8042),(96,0x10042)):
            raw=self.superblock();struct.pack_into("<I",raw,offset,value)
            with self.subTest(offset=offset,value=value),self.assertRaises(ValueError):
                r._geometry(bytes(raw))

    def test_filetype_required_in_the_incompatible_feature_field(self):
        self.assertEqual(0x2, r.EXT4_FEATURE_INCOMPAT_FILETYPE)
        for compat, rocompat in ((0x4, 0), (0x6, 0), (0x4, 0x2), (0x6, 0x2)):
            raw = self.superblock()
            # FILETYPE belongs to incompat. Numerically equal bits in the
            # other namespaces cannot supply the missing directory type bit.
            struct.pack_into("<III", raw, 92, compat, 0x40, rocompat)
            with self.subTest(compat=compat, rocompat=rocompat):
                with self.assertRaisesRegex(ValueError, "HOST_WINDOW_EXT4_GEOMETRY"):
                    r._geometry(bytes(raw))
                struct.pack_into("<I", raw, 96, 0x42)
                self.assertEqual((4096, 4096), r._geometry(bytes(raw)))

    def test_ea_inode_rejected_from_the_incompatible_feature_field(self):
        # The same numeric bit in compat/rocompat has a different meaning.
        # These controls preserve parsing behavior, not full FS qualification.
        for compat, rocompat in ((0x4, 0), (0x404, 0), (0x4, 0x400), (0x404, 0x400)):
            raw = self.superblock()
            struct.pack_into("<III", raw, 92, compat, 0x42, rocompat)
            with self.subTest(compat=compat, rocompat=rocompat):
                self.assertEqual((4096, 4096), r._geometry(bytes(raw)))
                struct.pack_into("<I", raw, 96, 0x442)
                with self.assertRaisesRegex(ValueError, "HOST_WINDOW_EXT4_GEOMETRY"):
                    r._geometry(bytes(raw))


if __name__=="__main__":unittest.main()
