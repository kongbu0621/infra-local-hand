"""Real journal device admission over synthetic block/sysfs boundaries only."""
from __future__ import annotations

import os
import stat
import struct
import sys
import uuid
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux journal device admission", allow_module_level=True)

from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g


UUID = "11111111-2222-3333-4444-555555555555"
SERIAL = "fixture-journal"


@pytest.fixture
def block_boundary(monkeypatch):
    """Substitute kernel I/O, retaining JournalDevice's complete constructor."""
    trace = []
    device_path = "/dev/vdc"
    rdev = os.makedev(253, 2)
    syslink = "/sys/dev/block/253:2"
    syspath = "/sys/devices/pci0000:00/0000:00:05.0/virtio2/block/vdc"
    target = "../../devices/pci0000:00/0000:00:05.0/virtio2/block/vdc"
    info = SimpleNamespace(st_dev=7, st_ino=101, st_mode=stat.S_IFBLK | 0o660,
        st_uid=0, st_gid=6, st_nlink=1, st_size=0, st_mtime_ns=10,
        st_ctime_ns=11, st_atime_ns=12, st_rdev=rdev)
    row = dict(role="journal", path="/fixture/journal", directory=dict(dev=rdev),
        filesystem=dict(uuid=UUID, mount=dict(root="/", fstype="ext4",
            path="/fixture/journal", options=["rw"], source=device_path, device=rdev)))
    observed = [None]

    def check():
        trace.append("check")

    def open_path(path, *, block=False):
        assert path == device_path and block is True
        trace.append("open")
        return 91

    def fstat(fd):
        assert fd == 91
        return info

    def named_stat(path, *, follow_symlinks):
        assert follow_symlinks is False
        if path == syspath + "/partition":
            raise FileNotFoundError(path)
        assert path == device_path
        return info

    def readlink(path):
        assert path == syslink
        return target

    def realpath(path):
        assert path == syslink
        return syspath

    def read_kernel(path, cap, guard, *, expected_fs):
        assert expected_fs == 0x62656572 and guard is check
        guard()
        if path == syspath + "/serial":
            assert cap == 128
            trace.append("serial")
            return observed[0]
        assert path == syspath + "/size" and cap == 64
        trace.append("size")
        return str(g.OLD_SIZE // 512).encode("ascii") + b"\n"

    def ioctl(fd, operation, output, mutate):
        assert fd == 91 and operation == 0x80081272 and mutate is True
        trace.append("ioctl")
        output[:] = struct.pack("=Q", g.OLD_SIZE)
        return 0

    def pread(fd, amount, offset):
        assert (fd, amount, offset) == (91, 1024, 1024)
        trace.append("superblock")
        raw = bytearray(1024)
        struct.pack_into("<I", raw, 4, g.OLD_SIZE // 4096)
        struct.pack_into("<I", raw, 24, 2)
        raw[56:58] = b"\x53\xef"
        raw[104:120] = uuid.UUID(UUID).bytes
        return bytes(raw)

    def close(fd):
        assert fd == 91
        trace.append("close")

    # Namespace copies avoid changing the interpreter's or other modules' os.
    fake_os = SimpleNamespace(**vars(g.os))
    fake_os.path = SimpleNamespace(**vars(g.os.path))
    fake_os.fstat, fake_os.stat, fake_os.readlink = fstat, named_stat, readlink
    fake_os.path.realpath, fake_os.pread, fake_os.close = realpath, pread, close
    monkeypatch.setattr(g, "os", fake_os)
    monkeypatch.setattr(g, "fcntl", SimpleNamespace(ioctl=ioctl))
    monkeypatch.setattr(g, "open_path", open_path)
    monkeypatch.setattr(g, "read_kernel", read_kernel)

    def construct(raw, expected=SERIAL):
        observed[0] = raw
        return g.JournalDevice(row, expected, g.OLD_SIZE, check)

    return construct, trace


@pytest.mark.parametrize("serial", ["x", SERIAL, "A" * 20])
def test_device_accepts_exact_linux_virtio_serial_without_newline(block_boundary, serial):
    construct, trace = block_boundary
    device = construct(serial.encode("ascii"), serial)
    try:
        assert device.report()["serial"] == serial
        assert device.report()["superblock"]["uuid"] == UUID
        assert trace.index("serial") < trace.index("ioctl") < trace.index("superblock")
        assert "close" not in trace
    finally:
        device.close()
    assert trace.count("close") == 1


@pytest.mark.parametrize("raw", [
    b"", b"wrong-journal", SERIAL[:-1].encode("ascii"),
    SERIAL.encode("ascii") + b"\n", SERIAL.encode("ascii") + b"\r\n",
    SERIAL.encode("ascii") + b"\x00", SERIAL.encode("ascii") + b"\x00" * 5,
    b" " + SERIAL.encode("ascii"), SERIAL.encode("ascii") + b" ",
    SERIAL.encode("ascii") + b"\t", SERIAL.encode("ascii") + b"extra",
    SERIAL.encode("ascii") + b"\xff",
])
def test_device_serial_mismatch_stops_before_size_or_superblock_and_closes_fd(block_boundary, raw):
    construct, trace = block_boundary
    with pytest.raises(g.r.ObservationError, match="^GROWTH_JOURNAL_SERIAL$") as failure:
        construct(raw)
    assert failure.value.serial_diagnostic == dict(expected_bytes=len(SERIAL), actual_bytes=len(raw),
        expected_hex=SERIAL.encode("ascii").hex(), actual_hex=raw.hex())
    assert trace.count("serial") == trace.count("close") == 1
    assert not {"ioctl", "size", "superblock"}.intersection(trace)


def test_device_does_not_accept_truncated_twenty_byte_identity(block_boundary):
    construct, trace = block_boundary
    with pytest.raises(g.r.ObservationError, match="^GROWTH_JOURNAL_SERIAL$"):
        construct(b"A" * 19, "A" * 20)
    assert "ioctl" not in trace and trace.count("close") == 1


def description(serial):
    paths = {role: "/fixture/" + role for role in g.r.ROLES}
    return dict(schema=g.SCHEMA, guest_startup_assurance=g.guest_startup_assurance(), session=g.SESSION, phase="pre", nonce="a" * 64,
        source_binding_sha256="b" * 64, paths=paths,
        saved_rows=[dict(role=role, path=paths[role], filesystem=dict(uuid=UUID)) for role in g.r.ROLES],
        original_boot_id=UUID, journal_serial=serial,
        expected_units=[dict(name="old.service", control_group="/old.service")],
        domain_cgroups=["/old.slice"],
        domain_units=[dict(name="old.slice", manager="system", control_group="/old.slice")],
        protected_roots=["/fixture"], essential_paths=["/fixture/evidence"],
        window_seconds=900, change_seconds=780)


@pytest.mark.parametrize("serial", ["x", "A" * 20])
def test_descriptor_accepts_full_virtio_identity_domain(serial):
    value = description(serial)
    assert g.descriptor(g.canonical(value))["journal_serial"] == serial


@pytest.mark.parametrize("serial", ["", "A" * 21, "A" * 64, "A" * 128,
    "has space", "has\nnewline", "has\x00nul", "非ASCII"])
def test_descriptor_rejects_serial_that_cannot_bind_exactly(serial):
    with pytest.raises(g.r.ObservationError, match="^GROWTH_SERIAL$"):
        g.descriptor(g.canonical(description(serial)))


@pytest.fixture
def image_boundary(tmp_path, monkeypatch):
    argv = ["/usr/bin/qemu-system-x86_64"]
    for name in ("system.qcow2", "quota.qcow2", "journal.qcow2", "evidence.qcow2", "seed.iso"):
        path = tmp_path / name
        path.write_bytes(b"synthetic-image")
        path.chmod(0o600)
        options = "format=raw,readonly=on" if name.endswith("iso") else "format=qcow2"
        if name == "journal.qcow2":
            options += ",id=journal_drive"
        argv += ["-drive", options + ",file=" + str(path)]
    monkeypatch.setattr(h.local, "open_directory", lambda path, owner:
        os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW))
    anchor = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        def construct(serial):
            return h.ImageSet(anchor, str(tmp_path), [*argv, "-device",
                "virtio-blk-pci,drive=journal_drive,serial=" + serial], lambda: None)
        yield construct
    finally:
        os.close(anchor)


@pytest.mark.parametrize("serial", ["x", "A" * 20])
def test_host_derived_serial_accepts_full_virtio_identity_domain(image_boundary, serial):
    images = image_boundary(serial)
    try:
        assert images.journal_serial == serial
    finally:
        images.close()


@pytest.mark.parametrize("serial", ["", "A" * 21, "A" * 64, "A" * 128,
    "has space", "has\nnewline", "has\x00nul", "非ASCII"])
def test_host_rejects_serial_that_would_be_truncated_by_virtio(image_boundary, serial):
    with pytest.raises(h.prior.r.ObservationError, match="^GROWTH_JOURNAL_SERIAL$"):
        images = image_boundary(serial)
        images.close()
