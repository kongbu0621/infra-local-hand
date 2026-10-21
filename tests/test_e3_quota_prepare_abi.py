"""Prepare UAPI layout/encoding tests, not live quota or platform acceptance.

The native witness only prints installed Linux header facts. Quota calls are
mocked; no accounts, services, mounts or quota domains are created.
"""
import ctypes
import errno
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "_prepare_abi_test", ROOT / "tests/e3_host/q2_prepare.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SUPPORTED = (sys.platform == "linux" and platform.machine() in {"x86_64", "aarch64"}
             and sys.byteorder == "little" and ctypes.sizeof(ctypes.c_void_p) == 8)


def layout(kind):
    return dict(size=ctypes.sizeof(kind), alignment=ctypes.alignment(kind),
                offsets=[getattr(kind, name).offset for name, _ in kind._fields_])


@unittest.skipUnless(SUPPORTED, "Linux little-endian LP64 quota UAPI")
class PrepareABI(unittest.TestCase):
    def test_native_header_layout_matches_every_ctypes_field(self):
        cc = shutil.which("cc")
        if not cc:
            self.skipTest("C compiler unavailable; native ABI evidence NOT obtained")
        with tempfile.TemporaryDirectory(prefix="lh-prepare-abi-") as folder:
            binary = Path(folder) / "layout"
            subprocess.run(
                [cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                 str(ROOT / "tests/fixtures/quota_prepare_layout.c"), "-o", str(binary)],
                check=True, capture_output=True, timeout=30)
            result = subprocess.run([str(binary)], check=True, capture_output=True, timeout=5)
        self.assertEqual(b"", result.stderr)
        native = json.loads(result.stdout)
        quota = m.Quota("/synthetic/device")
        self.assertIs(native["little_endian"], True)
        self.assertEqual([8, 8, 4, 8, 8], native["scalars"])
        self.assertEqual(layout(quota.Block), native["nextdqblk"])
        self.assertEqual(layout(quota.State), native["state"])
        file_type = dict(quota.State._fields_)["user"]
        self.assertEqual(layout(file_type), native["file"])
        # GET/SET use the common prefix; the project field occupies dqblk's
        # final padding. Both kernel writes fit the same aligned allocation.
        self.assertEqual(native["dqblk"]["size"], ctypes.sizeof(quota.Block))
        self.assertEqual(native["dqblk"]["alignment"], ctypes.alignment(quota.Block))
        self.assertEqual(native["dqblk"]["offsets"], layout(quota.Block)["offsets"][:-1])
        self.assertEqual([0x800007, 0x800009, 0x800008, (ord("X") << 8) | 8,
                          2, 1024, 1, 48, quota.VALID_ALL], native["constants"])

    def test_platform_allowlist_does_not_admit_unknown_abis(self):
        # This tests the guard, not execution on the substituted architecture.
        for system, machine, endian in (
            ("win32", "aarch64", "little"), ("linux", "armv7l", "little"),
            ("linux", "riscv64", "little"), ("linux", "x86_64", "big"),
            ("linux", "aarch64_be", "big"),
        ):
            with self.subTest(system=system, machine=machine, endian=endian), \
                    mock.patch.object(m.sys, "platform", system), \
                    mock.patch.object(platform, "machine", return_value=machine), \
                    mock.patch.object(m.sys, "byteorder", endian), \
                    mock.patch.object(ctypes, "CDLL") as load:
                with self.assertRaisesRegex(ValueError, "PREPARE_QUOTA_ABI"):
                    m.Quota("/synthetic/device")
                load.assert_not_called()

    def test_layout_and_width_drift_rejected_before_loading_libc(self):
        size, alignment = ctypes.sizeof, ctypes.alignment
        cases = (
            (lambda kind: 4 if kind is ctypes.c_void_p else size(kind), alignment),
            (lambda kind: 4 if kind is ctypes.c_long else size(kind), alignment),
            (lambda kind: 8 if kind is ctypes.c_int else size(kind), alignment),
            (lambda kind: 76 if getattr(kind, "__name__", "") == "Block" else size(kind), alignment),
            (lambda kind: 152 if getattr(kind, "__name__", "") == "State" else size(kind), alignment),
            (size, lambda kind: 4 if getattr(kind, "__name__", "") == "Block" else alignment(kind)),
        )
        for sizes, alignments in cases:
            with self.subTest(sizes=sizes, alignments=alignments), \
                    mock.patch.object(ctypes, "sizeof", side_effect=sizes), \
                    mock.patch.object(ctypes, "alignment", side_effect=alignments), \
                    mock.patch.object(ctypes, "CDLL") as load:
                with self.assertRaisesRegex(ValueError, "PREPARE_QUOTA_ABI"):
                    m.Quota("/synthetic/device")
                load.assert_not_called()

    def test_signed_command_and_high_project_keep_original_u32_bits(self):
        quota = m.Quota("/synthetic/device")
        quota.lib = mock.Mock()
        quota.lib.quotactl.return_value = 0
        quota.call(0x800007, 0xfffffffe, quota.Block())
        command, device, project, _ = quota.lib.quotactl.call_args.args
        self.assertEqual(0x80000702, command.value & 0xffffffff)
        self.assertEqual(0xfffffffe, project.value & 0xffffffff)
        self.assertEqual(b"/synthetic/device", device)

    def test_errno_is_captured_and_stale_errno_cannot_turn_success_into_failure(self):
        quota = m.Quota("/synthetic/device")
        def denied(*_):
            ctypes.set_errno(errno.EPERM)
            return -1
        quota.lib = mock.Mock()
        quota.lib.quotactl.side_effect = denied
        with self.assertRaises(OSError) as error:
            quota.block(73)
        self.assertEqual(errno.EPERM, error.exception.errno)
        def success(command, device, project, pointer):
            ctypes.cast(pointer, ctypes.POINTER(quota.Block)).contents.valid = 63
            return 0
        quota.lib.quotactl.side_effect = success
        ctypes.set_errno(errno.EIO)
        self.assertEqual(0, quota.block(73)["hard"])

    def test_enforcement_requires_version_and_both_project_flags(self):
        quota = m.Quota("/synthetic/device")
        for version, flags in ((1, 48), (1, 16), (1, 32), (1, 3), (2, 48)):
            def observe(command, project, state):
                self.assertEqual((ord("X") << 8) | 8, command)
                self.assertEqual(0, project)
                self.assertIsInstance(state, quota.State)
                self.assertEqual(1, state.version)
                state.version, state.flags = version, flags
            quota.call = observe
            with self.subTest(version=version, flags=flags):
                if (version, flags) == (1, 48):
                    self.assertEqual(48, quota.enforcement())
                else:
                    with self.assertRaisesRegex(ValueError, "PREPARE_QUOTA_ENFORCEMENT"):
                        quota.enforcement()

    def test_missing_validity_cannot_establish_unused_project_or_inventory(self):
        quota = m.Quota("/synthetic/device")

        def empty_return(command, project, result):
            if command == 0x800009 and project:
                raise OSError(errno.ENOENT, "end")
            # A successful syscall with an untouched buffer is NOT evidence
            # that limits, usage and timers are all zero.

        quota.call = mock.Mock(side_effect=empty_return)
        for operation in (lambda: quota.unused(73), lambda: quota.inventory(lambda: None)):
            with self.subTest(operation=operation), \
                    self.assertRaisesRegex(ValueError, "PREPARE_QUOTA_VALID"):
                operation()

    def test_all_consumed_fields_need_validity_but_unknown_extra_bits_are_tolerated(self):
        quota = m.Quota("/synthetic/device")
        for mask in (*range(63), *(63 ^ (1 << bit) | 128 for bit in range(6)), 63, 191):
            def observe(command, project, result):
                if command == 0x800009 and project:
                    raise OSError(errno.ENOENT, "end")
                result.valid = mask
            quota.call = mock.Mock(side_effect=observe)
            for kind in ("block", "unused", "inventory"):
                with self.subTest(mask=mask, kind=kind):
                    operation = (lambda: quota.inventory(lambda: None)) if kind == "inventory" else (
                        lambda: getattr(quota, kind)(73))
                    if mask & 63 != 63:
                        with self.assertRaisesRegex(ValueError, "PREPARE_QUOTA_VALID"):
                            operation()
                    else:
                        result = operation()
                        if kind == "block":
                            self.assertEqual(mask, result["valid"])
                        elif kind == "inventory":
                            self.assertEqual([0], [row["project"] for row in result])
                            self.assertEqual(mask, result[0]["valid"])
                        else:
                            self.assertIsNone(result)

    def test_setquota_retains_its_selected_field_mask(self):
        quota = m.Quota("/synthetic/device")
        quota.lib = mock.Mock()
        quota.lib.quotactl.return_value = 0
        limits = quota.Block()
        limits.hard, limits.ihard, limits.valid = 4096, 1024, 5
        quota.call(0x800008, 73, limits)
        command, _, project, pointer = quota.lib.quotactl.call_args.args
        self.assertEqual(0x80000802, command.value & 0xffffffff)
        self.assertEqual(73, project.value)
        observed = ctypes.cast(pointer, ctypes.POINTER(quota.Block)).contents
        self.assertEqual((4096, 1024, 5), (observed.hard, observed.ihard, observed.valid))

    def test_read_failure_is_not_empty_and_a_later_read_can_retry(self):
        quota = m.Quota("/synthetic/device")
        for kind in ("block", "unused", "inventory"):
            with self.subTest(kind=kind):
                calls = []
                def observe(command, project, result):
                    calls.append((command, project))
                    if len(calls) == 1:
                        raise OSError(errno.EIO, "synthetic read failure")
                    if command == 0x800009 and project:
                        raise OSError(errno.ENOENT, "end")
                    result.valid = 63
                quota.call = observe
                operation = (lambda: quota.inventory(lambda: None)) if kind == "inventory" else (
                    lambda: getattr(quota, kind)(73))
                with self.assertRaises(OSError) as error:
                    operation()
                self.assertEqual(errno.EIO, error.exception.errno)
                self.assertEqual(1, len(calls))  # no hidden retry or empty fallback
                operation()  # failure did not permanently freeze a read-only observer


if __name__ == "__main__":
    unittest.main()
