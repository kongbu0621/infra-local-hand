"""Synthetic image/process fixtures; no original guest or process inventory."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux process and file descriptors", allow_module_level=True)

from e3_host import q2_journal_growth as h


def stat_bytes(pid, start=12):
    return (str(pid) + " (fixture worker) " + " ".join(["S", *(["0"] * 18), str(start)])).encode()


def process_fixture(root, image, *, pid=27, flags="0100002", mapping=False):
    process = root / str(pid)
    task = process / "task" / str(pid)
    (task / "fd").mkdir(parents=True)
    (task / "fdinfo").mkdir()
    (process / "stat").write_bytes(stat_bytes(pid))
    (task / "stat").write_bytes(stat_bytes(pid))
    if not mapping:
        (task / "fd/8").symlink_to(image)
        (task / "fdinfo/8").write_text("pos:\t0\nflags:\t" + flags + "\n")
    info = image.stat()
    maps = (f"1000-2000 rw-s 00000000 {os.major(info.st_dev):02x}:{os.minor(info.st_dev):02x} "
            f"{info.st_ino} {image}\n") if mapping else ""
    (task / "maps").write_text(maps)
    return task


def test_inode_writer_fds_and_mapped_writer(tmp_path):
    image = tmp_path / "image"
    image.write_bytes(b"fixture")
    root = tmp_path / "proc"
    process_fixture(root, image)
    process_fixture(root, image, pid=28, mapping=True)
    key = {"journal": (image.stat().st_dev, image.stat().st_ino)}
    rows = h.collect_image_writers(key, lambda: None, proc_root=str(root))
    assert [(row["pid"], row["writable_images"]) for row in rows] == [(27, ["journal"]), (28, ["journal"])]
    with pytest.raises(h.prior.r.ObservationError, match="UNEXPECTED_WRITER"):
        h.verify_writers(rows, 27, ["journal"])


def test_readonly_fd_is_not_a_writer(tmp_path):
    image = tmp_path / "image"
    image.write_bytes(b"fixture")
    root = tmp_path / "proc"
    process_fixture(root, image, flags="0100000")
    rows = h.collect_image_writers({"journal": (image.stat().st_dev, image.stat().st_ino)},
                                   lambda: None, proc_root=str(root))
    h.verify_writers(rows, None, ["journal"])


@pytest.mark.parametrize("failure", ["permission", "vanished", "flags", "maps"])
def test_unknown_inventory_never_becomes_empty(tmp_path, monkeypatch, failure):
    image = tmp_path / "image"
    image.write_bytes(b"fixture")
    root = tmp_path / "proc"
    task = process_fixture(root, image)
    if failure == "permission":
        original = h._proc_read
        def unreadable(path, cap, check, *context, **options):
            if path.endswith("/maps"):
                raise PermissionError("fixture")
            return original(path, cap, check, *context, **options)
        monkeypatch.setattr(h, "_proc_read", unreadable)
    elif failure == "vanished":
        (task / "fdinfo/8").unlink()
    elif failure == "flags":
        (task / "fdinfo/8").write_text("flags:\t0100002\nflags:\t0100000\n")
    else:
        (task / "maps").write_text("unparseable\n")
    with pytest.raises(h.prior.r.ObservationError):
        h.collect_image_writers({"journal": (image.stat().st_dev, image.stat().st_ino)},
                               lambda: None, proc_root=str(root))


def test_thread_private_fd_table_is_included(tmp_path):
    image = tmp_path / "image"
    image.write_bytes(b"fixture")
    root = tmp_path / "proc"
    task = process_fixture(root, image, flags="0100000")
    second = task.parent / "28"
    (second / "fd").mkdir(parents=True)
    (second / "fdinfo").mkdir()
    (second / "stat").write_bytes(stat_bytes(28))
    (second / "maps").write_text("")
    (second / "fd/4").symlink_to(image)
    (second / "fdinfo/4").write_text("flags:\t0100002\n")
    rows = h.collect_image_writers({"journal": (image.stat().st_dev, image.stat().st_ino)},
                                   lambda: None, proc_root=str(root))
    assert rows[0]["writable_images"] == ["journal"]


def test_self_fd_snapshot_does_not_stat_closed_scanner(tmp_path):
    path = tmp_path / "self-image"
    path.write_bytes(b"fixture")
    fd = os.open(path, os.O_RDONLY)
    try:
        held = os.fstat(fd)
        try:
            viewed = os.stat(f"/proc/self/fd/{fd}")
        except OSError:
            pytest.skip("native self fd/proc view unavailable")
        if h.identity(viewed) != h.identity(held):
            pytest.skip("native self fd/proc namespace mismatch")
        first = h._fd_snapshot("/proc/self/fd", lambda: None)
        second = h._fd_snapshot("/proc/self/fd", lambda: None)
        assert h.identity(first[str(fd)]) == h.identity(held)
        assert {n: h.identity(s) for n, s in first.items()} == {n: h.identity(s) for n, s in second.items()}
    finally:
        os.close(fd)


@pytest.fixture
def images(tmp_path, monkeypatch):
    names = ("system.qcow2", "quota.qcow2", "journal.qcow2", "evidence.qcow2", "seed.iso")
    argv = ["/usr/bin/qemu-system-x86_64"]
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"synthetic-image")
        path.chmod(0o600)
        options = "format=raw,readonly=on" if name.endswith("iso") else "format=qcow2"
        if name == "journal.qcow2":
            options += ",id=journal_drive"
        argv += ["-drive", options + ",file=" + str(path)]
    argv += ["-device", "virtio-blk-pci,drive=journal_drive,serial=fixture-journal"]
    monkeypatch.setattr(h.local, "open_directory", lambda path, owner:
                        os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW))
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    value = h.ImageSet(fd, str(tmp_path), argv, lambda: None)
    yield value
    value.close()
    os.close(fd)


def test_image_set_detects_replacement_and_unknown_writes(images):
    assert images.journal_serial == "fixture-journal"
    path = Path(images.paths["journal"])
    path.rename(path.with_name("old"))
    path.write_bytes(b"replacement")
    path.chmod(0o600)
    with pytest.raises(h.prior.r.ObservationError, match="IMAGE_DRIFT"):
        images.recheck()


def test_offline_nonjournal_write_not_exempted(images):
    images.checkpoint()
    Path(images.paths["quota"]).write_bytes(b"drift")
    with pytest.raises(h.prior.r.ObservationError, match="IMAGE_WRITE"):
        images.recheck(stable=True, journal_changed=True)


def test_live_write_allowed_but_seed_remains_immutable(images):
    Path(images.paths["journal"]).write_bytes(b"normal live write")
    images.recheck()
    with pytest.raises(h.prior.r.ObservationError, match="IMAGE_WRITE"):
        images.recheck(stable=True)
    images.checkpoint()
    images.recheck(stable=True)
    Path(images.paths["seed"]).write_bytes(b"unexpected write")
    with pytest.raises(h.prior.r.ObservationError, match="IMAGE_WRITE"):
        images.recheck()


@pytest.mark.parametrize("changed", ["path", "hardlink", "permissions"])
def test_image_set_rejects_alias_and_permissions(images, tmp_path, changed):
    path = Path(images.paths["quota"])
    if changed == "path":
        path.rename(path.with_name("saved"))
        path.symlink_to(path.with_name("saved"))
    elif changed == "hardlink":
        os.link(path, tmp_path / "second-link")
    else:
        path.chmod(0o644)
    with pytest.raises(h.prior.r.ObservationError):
        images.recheck()


def test_pidfile_strict_locator(tmp_path):
    path = tmp_path / "vm.pid"
    path.write_bytes(b"123\n")
    path.chmod(0o600)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        assert h.pidfile(fd, "vm.pid", lambda: None) == 123
        for raw in (b"1\n", b"123\n456\n", b"12 ", b"-2", b"", b"012"):
            path.write_bytes(raw)
            with pytest.raises(h.prior.r.ObservationError):
                h.pidfile(fd, "vm.pid", lambda: None)
    finally:
        os.close(fd)


def test_grow_uses_only_normal_locking_and_compare(images):
    calls = []
    def run(args):
        calls.append(args)
        if args[0] == "info":
            data = {"format": "qcow2", "virtual-size": h.NEW_SIZE,
                    "format-specific": {"data": {"compat": "1.1", "corrupt": False}}}
        else:
            data = {}
        return dict(stdout=h.canonical(data), stderr=b"", returncode=0, eof={"stdout": True, "stderr": True})
    images.checkpoint()
    images.grow(SimpleNamespace(run=run), images.anchor + "/" + h.NAMES["journal.backup.qcow2"])
    assert [args[0] for args in calls] == ["resize", "info", "check", "compare"]
    assert not {"-r", "-U", "--force", "--shrink"} & {part for args in calls for part in args}
