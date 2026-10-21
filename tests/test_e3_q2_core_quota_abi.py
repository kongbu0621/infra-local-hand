"""Native layout and read-only capacity ABI checks; no live quota calls."""
import ctypes
import errno
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from unittest import mock

import pytest

from test_e3_q2_core_candidate_loader import d

SUPPORTED = (sys.platform == "linux" and platform.machine() in {"aarch64", "x86_64"}
             and sys.byteorder == "little" and ctypes.sizeof(ctypes.c_void_p) == 8)
pytestmark = pytest.mark.skipif(not SUPPORTED, reason="Native Linux little-endian LP64 ABI required")


def layout(kind):
    return dict(size=ctypes.sizeof(kind), alignment=ctypes.alignment(kind),
                offsets=[getattr(kind, key).offset for key, _ in kind._fields_])


def test_native_header_matches_capacity_and_preparation_layouts(tmp_path):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("Native compiler unavailable; no ABI evidence obtained")
    binary = tmp_path / "layout"
    subprocess.run([cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                    str(Path(__file__).parent / "fixtures/quota_prepare_layout.c"),
                    "-o", str(binary)], check=True, capture_output=True, timeout=30)
    result = subprocess.run([str(binary)], check=True, capture_output=True, timeout=5)
    assert result.stderr == b""
    native = json.loads(result.stdout)
    from test_e3_quota_prepare_abi import m
    reader, prepare = d._CapQuota("/unused"), m.Quota("/unused")
    for quota in (reader, prepare):
        assert native["little_endian"] is True
        assert native["scalars"] == [8, 8, 4, 8, 8]
        assert layout(quota.Block) == native["nextdqblk"]
        assert layout(quota.State) == native["state"]
        assert layout(dict(quota.State._fields_)["user"]) == native["file"]
        assert native["dqblk"] == dict(size=72, alignment=8,
                                       offsets=layout(quota.Block)["offsets"][:-1])
        assert native["constants"] == [0x800007, 0x800009, 0x800008,
                                      (ord("X") << 8) | 8, 2, 1024, 1, 48, quota.VALID_ALL]


@pytest.mark.parametrize("system,machine,endian", [
    ("Windows", "aarch64", "little"), ("Linux", "armv7l", "little"),
    ("Linux", "riscv64", "little"), ("Linux", "aarch64", "big"),
    ("Linux", "x86_64", "big"),
])
def test_unknown_platforms_rejected_before_loading_libc(system, machine, endian):
    with mock.patch.object(platform, "system", return_value=system), \
            mock.patch.object(platform, "machine", return_value=machine), \
            mock.patch.object(sys, "byteorder", endian), mock.patch.object(ctypes, "CDLL") as load:
        with pytest.raises(d.DispatchError, match="QUOTA_ABI"):
            d._CapQuota("/unused")
        load.assert_not_called()


@pytest.mark.parametrize("kind", ["pointer", "long", "int", "block", "state", "alignment"])
def test_layout_drift_rejected_before_loading_libc(kind):
    size, alignment = ctypes.sizeof, ctypes.alignment
    target = {"pointer": ctypes.c_void_p, "long": ctypes.c_long, "int": ctypes.c_int}.get(kind)

    def sizes(value):
        if value is target:
            return 4 if kind != "int" else 8
        if (kind, getattr(value, "__name__", "")) in {("block", "Block"), ("state", "State")}:
            return size(value) + 8
        return size(value)

    with mock.patch.object(ctypes, "sizeof", side_effect=sizes), \
            mock.patch.object(ctypes, "alignment",
                side_effect=lambda value: 4 if kind == "alignment" and
                getattr(value, "__name__", "") == "Block" else alignment(value)), \
            mock.patch.object(ctypes, "CDLL") as load:
        with pytest.raises(d.DispatchError, match="QUOTA_ABI"):
            d._CapQuota("/unused")
        load.assert_not_called()


def test_capacity_reads_require_all_consumed_fields_and_allow_extra_valid_bits():
    quota = d._CapQuota("/unused")
    for mask in (*range(63), *(63 ^ (1 << bit) | 128 for bit in range(6)), 63, 191):
        def observe(command, project, result):
            if command == 0x800009 and project:
                raise OSError(errno.ENOENT, "inventory ended")
            result.valid = mask
        with mock.patch.object(quota, "call", side_effect=observe):
            for read in (lambda: quota.block(73), lambda: quota.unused(73),
                         lambda: quota.inventory(lambda: None)):
                if mask & 63 != 63:
                    with pytest.raises(d.DispatchError, match="QUOTA_VALID"):
                        read()
                else:
                    read()


def test_every_nonzero_usage_limit_or_timer_prevents_unused_admission():
    quota = d._CapQuota("/unused")
    for field in ("hard", "soft", "space", "ihard", "isoft", "inodes", "btime", "itime"):
        def observe(command, project, result):
            result.valid = 63
            setattr(result, field, 1)
        with mock.patch.object(quota, "call", side_effect=observe):
            with pytest.raises(d.DispatchError, match="PROJECT_OCCUPIED"):
                quota.unused(73)


def test_enforcement_requires_typed_state_version_and_both_project_flags():
    quota = d._CapQuota("/unused")
    for version, flags in ((1, 48), (1, 16), (1, 32), (1, 3), (2, 48)):
        def observe(command, project, state):
            assert (command, project) == ((ord("X") << 8) | 8, 0)
            assert isinstance(state, quota.State) and state.version == 1
            state.version, state.flags = version, flags
        with mock.patch.object(quota, "call", side_effect=observe):
            if (version, flags) == (1, 48):
                assert quota.enforcement() == 48
            else:
                with pytest.raises(d.DispatchError, match="QUOTA_ENFORCEMENT"):
                    quota.enforcement()


def test_signed_command_id_errno_and_read_only_allowlist():
    quota = d._CapQuota("/unused")
    quota.lib = mock.Mock()
    quota.lib.quotactl.return_value = 0
    ctypes.set_errno(errno.EIO)
    quota.call(0x800007, 0xfffffffe, quota.Block())
    command, device, project, _ = quota.lib.quotactl.call_args.args
    assert (command.value & 0xffffffff, device, project.value & 0xffffffff) == (
        0x80000702, b"/unused", 0xfffffffe)
    for command in (0x800008, 0, (ord("X") << 8) | 4):
        quota.lib.reset_mock()
        with pytest.raises(d.DispatchError, match="QUOTA_READ_ONLY"):
            quota.call(command, 73, quota.Block())
        quota.lib.quotactl.assert_not_called()
    def denied(*args):
        ctypes.set_errno(errno.EPERM)
        return -1
    quota.lib.quotactl.side_effect = denied
    with pytest.raises(OSError) as caught:
        quota.block(73)
    assert caught.value.errno == errno.EPERM


def test_observation_error_is_not_empty_and_can_retry():
    quota = d._CapQuota("/unused")
    for read in (lambda: quota.block(73), lambda: quota.unused(73),
                 lambda: quota.inventory(lambda: None)):
        with mock.patch.object(quota, "call", side_effect=OSError(errno.EIO, "read failed")):
            with pytest.raises(OSError) as caught:
                read()
            assert caught.value.errno == errno.EIO
        def recovered(command, project, result):
            if command == 0x800009 and project:
                raise OSError(errno.ENOENT, "end")
            result.valid = 63
        with mock.patch.object(quota, "call", side_effect=recovered):
            read()
