"""Synthetic image/process fixtures; no original guest or process inventory."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux process and file descriptors", allow_module_level=True)

from e3_host import q2_journal_growth as h


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
