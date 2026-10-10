"""Existing read failures survive guest, pipe and coordinator boundaries."""
import copy
import errno
import os
import stat
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux maintenance failures", allow_module_level=True)

from e3_host import q2_journal_growth as h, q2_journal_growth_guest as g
from test_e3_q2_journal_growth_transport import factory, NONCE, SHA, BOOT
from test_e3_q2_journal_growth_coordinator import rig


def maintenance(inventory):
    value = g.GuestMaintenance(dict(phase="pre", nonce=NONCE,
        source_binding_sha256=SHA, guest_startup_assurance=g.guest_startup_assurance()),
        window=SimpleNamespace(check=lambda **_: None))
    value.inventory = inventory
    value.stage = "PRE_RUNTIME_PREPARATION"
    value.started = {"runtime_preparation"}
    return value


@pytest.fixture
def local_inventory(tmp_path, monkeypatch):
    """Map guest / to an owned fixture; all component opens/stats/closes are real."""
    root = tmp_path / "guest"
    root.mkdir(mode=0o700)
    (root / "evidence").mkdir(mode=0o700)
    calls = []
    real_open = os.open

    def open_fixture(path, flags, *args, **kwargs):
        calls.append(path)
        return real_open(root if path == "/" else path, flags, *args, **kwargs)

    synthetic_os = SimpleNamespace(**vars(os))
    synthetic_os.open = open_fixture
    monkeypatch.setattr(g, "os", synthetic_os)
    qualify = g.r.qualify
    monkeypatch.setattr(g.r, "qualify", lambda info: qualify(info, owner=os.getuid()))
    reads = []
    def kernel_read(path, cap, check):
        reads.append(path)
        assert path == "/proc/self/mountinfo" or path.startswith("/proc/self/fdinfo/")
        return b"mount" if path == "/proc/self/mountinfo" else b"fdinfo"
    monkeypatch.setattr(g.r, "kernel_read", kernel_read)
    device = root.stat().st_dev
    monkeypatch.setattr(g.r, "mounts", lambda _: {1: dict(fstype="ext4", options=["rw"],
        device=device, root="/", path="/", source="/dev/fixture", mount_id=1)})
    monkeypatch.setattr(g.r, "mount_id", lambda _: 1)
    monkeypatch.setattr(g.r, "fs_uuid", lambda _: BOOT)
    # The guest permits root and its fixed job owner. Match the ordinary test
    # owner only at this synthetic root boundary, keeping the actual walker.
    walker = g.open_path
    monkeypatch.setattr(g, "open_path", lambda path, **kw: walker(path,
        **(kw | {"owners": (os.getuid(),)})))
    inv = object.__new__(g.GuestInventory)
    inv.description = dict(essential_paths=["/evidence/receipt"])
    inv.context = dict(unit="stale.service")
    inv.check = lambda: None
    return inv, root, calls, reads


@pytest.mark.parametrize("missing_parent", [False, True])
def test_missing_required_object_preserves_exact_lookup_without_another_read(local_inventory, missing_parent):
    inv, root, calls, reads = local_inventory
    if missing_parent:
        (root / "evidence").rmdir()
    with pytest.raises(FileNotFoundError) as caught:
        inv.persistent()
    value = maintenance(inv).failure(caught.value)
    detail = value["diagnostic"]
    assert value["status"] == "INCOMPLETE" and value["reason"] == "GROWTH_GUEST_IO_OR_RUNTIME"
    assert detail["errno"] == errno.ENOENT and detail["error_type"] == "FileNotFoundError"
    assert detail["context"] == dict(operation="persistent_inventory", field="open",
        path_index=0, path_bytes=17, path_sha256=g.digest(b"/evidence/receipt"))
    assert detail["path_lookup"] == dict(operation="open_component", path_bytes=17,
        path_sha256=g.digest(b"/evidence/receipt"), component_index=0 if missing_parent else 1)
    assert calls == (["/", "evidence"] if missing_parent else ["/", "evidence", "receipt"])
    assert reads == ["/proc/self/mountinfo"]
    assert b"/evidence" not in g.canonical(value) and b"stale.service" not in g.canonical(value)
    assert value["nonce"] == NONCE and value["source_binding_sha256"] == SHA
    assert value["actions_started"] == ["runtime_preparation"]


def test_success_clears_persistent_context_and_failure_snapshot_is_stable(local_inventory):
    inv, root, _calls, _reads = local_inventory
    with pytest.raises(FileNotFoundError) as caught:
        inv.persistent()
    value = maintenance(inv).failure(caught.value)
    retained = copy.deepcopy(value)
    (root / "evidence" / "receipt").write_bytes(b"synthetic evidence")
    assert inv.persistent()["count"] == 1 and inv.context == {}
    assert value == retained


@pytest.mark.parametrize("fault", ["symlink", "writable"])
def test_path_context_never_weakens_existing_protection(local_inventory, fault):
    inv, root, _calls, _reads = local_inventory
    target = root / "evidence" / "receipt"
    if fault == "symlink":
        target.symlink_to("other")
    else:
        target.write_bytes(b"untrusted"); target.chmod(0o666)
    with pytest.raises((OSError, g.r.ObservationError)) as caught:
        inv.persistent()
    assert maintenance(inv).failure(caught.value)["status"] == "INCOMPLETE"
    assert inv.context["field"] == "open"


@pytest.mark.parametrize("fault", ["owner", "group_write", "other_write", "both", "ancestor", "root"])
def test_protection_failure_retains_the_rejected_stat_without_another_read(local_inventory, fault):
    inv, root, calls, reads = local_inventory
    target = root / "evidence" / "receipt"
    target.write_bytes(b"retained evidence"); target.chmod(0o600)
    failed_index = -1 if fault == "root" else 0 if fault == "ancestor" else 1
    if fault in ("root", "ancestor"):
        (root if fault == "root" else target.parent).chmod(0o770)
    elif fault in ("group_write", "both"):
        target.chmod(0o620)
    elif fault == "other_write":
        target.chmod(0o602)
    rejected = None
    sampled = []
    real_stat = os.fstat
    def sample(fd):
        nonlocal rejected
        info = real_stat(fd)
        if fault in ("owner", "both") and stat.S_ISREG(info.st_mode):
            # Only the returned owner differs; opens, FD identity and all I/O
            # remain real and require neither root nor an actual chown.
            info = SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino,
                st_uid=os.getuid() + 1, st_gid=info.st_gid, st_mode=info.st_mode)
        sampled.append(fd)
        rejected = info
        return info
    g.os.fstat = sample
    with pytest.raises(g.r.ObservationError) as caught:
        inv.persistent()
    expected = ("DIRECTORY_PROTECTION" if fault == "root" else
        "GROWTH_PATH_ANCESTOR" if fault == "ancestor" else "GROWTH_PATH_PROTECTION")
    value = maintenance(inv).failure(caught.value)
    assert value["reason"] == expected and value["status"] == "INCOMPLETE"
    assert value["diagnostic"]["path_lookup"] == dict(operation="qualify_root" if fault == "root"
        else "qualify_component", path_bytes=17, path_sha256=g.digest(b"/evidence/receipt"),
        component_index=failed_index, qualification=dict(dev=rejected.st_dev, ino=rejected.st_ino,
            uid=rejected.st_uid, gid=rejected.st_gid,
            mode=rejected.st_mode, allowed_uids=[0] if fault == "root" else [os.getuid()],
            forbidden_write_bits=0o022))
    assert calls == ["/", "evidence", "receipt"][:failed_index + 2]
    assert len(sampled) == len(calls) and reads == ["/proc/self/mountinfo"]
    for fd in set(sampled):
        with pytest.raises(OSError) as closed:
            real_stat(fd)
        assert closed.value.errno == errno.EBADF
    assert b"/evidence" not in g.canonical(value)


@pytest.mark.parametrize("fail_on", [1, 2, 3])
def test_stat_failure_does_not_reuse_previous_component_metadata(local_inventory, fail_on):
    inv, root, _calls, _reads = local_inventory
    target = root / "evidence" / "receipt"
    target.write_bytes(b"retained evidence"); target.chmod(0o600)
    samples = []
    def sample(fd):
        samples.append(fd)
        if len(samples) == fail_on:
            raise OSError(errno.EIO, "synthetic stat failure")
        return os.fstat(fd)
    g.os.fstat = sample
    with pytest.raises(OSError) as caught:
        inv.persistent()
    detail = maintenance(inv).failure(caught.value)["diagnostic"]
    assert detail["errno"] == errno.EIO
    assert "qualification" not in detail["path_lookup"]
    assert len(samples) == fail_on


def test_runtime_pool_stat_error_closes_open_fd_and_keeps_context(tmp_path, monkeypatch):
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    monkeypatch.setattr(g, "open_path", lambda *a, **kw: fd)
    synthetic_os = SimpleNamespace(**vars(os))
    def fail_stat(actual):
        assert actual == fd
        raise OSError(errno.EIO, "synthetic fstat error")
    synthetic_os.fstat = fail_stat
    monkeypatch.setattr(g, "os", synthetic_os)
    prep = object.__new__(g.RuntimePreparation)
    prep.inventory = SimpleNamespace(context={})
    prep.check = lambda: None
    with pytest.raises(OSError, match="synthetic fstat"):
        prep.pool("/run")
    with pytest.raises(OSError) as closed:
        os.fstat(fd)
    assert closed.value.errno == errno.EBADF
    assert prep.inventory.context == dict(operation="runtime_pool", field="stat",
        path_bytes=4, path_sha256=g.digest(b"/run"))


def guest_failure():
    inv = SimpleNamespace(context=dict(operation="persistent_inventory", field="open",
        path_index=0, path_bytes=17, path_sha256=g.digest(b"/evidence/receipt")))
    error = FileNotFoundError(errno.ENOENT, "synthetic private message", "/private/secret")
    return maintenance(inv).failure(error)


@pytest.mark.parametrize("protection", [False, True])
def test_real_failure_pipe_keeps_guest_error_and_never_sends_token(factory, local_inventory, protection):
    create, _store, root = factory
    value = guest_failure()
    if protection:
        inv, guest_root, _calls, _reads = local_inventory
        target = guest_root / "evidence" / "receipt"
        target.write_bytes(b"retained evidence"); target.chmod(0o620)
        with pytest.raises(g.r.ObservationError) as caught:
            inv.persistent()
        value = maintenance(inv).failure(caught.value)
        assert value["diagnostic"]["path_lookup"]["qualification"]["mode"] & 0o020
    raw = h.canonical(value)
    # stdout stays open until stderr is sent, just like the guest's failure path.
    code = "import sys\nsys.stderr.buffer.write(" + repr(raw) + ");sys.stderr.flush()\nsys.exit(3)\n"
    transport = create(code)
    with pytest.raises(h.prior.r.ObservationError, match="GROWTH_REPORT_MISSING") as caught:
        transport.receive_report()
    detail = caught.value.diagnostic
    assert detail["guest_failure"] == {key: value[key] for key in ("stage", "reason", "diagnostic")}
    assert detail["stderr"]["sha256"] == h.digest(raw)
    assert (root / h.NAMES["pre.stderr"]).read_bytes() == raw
    assert transport.report is None and not transport.sent
    assert not (root / h.NAMES["events.jsonl"]).exists()
    assert b"private/secret" not in h.canonical(detail)


@pytest.mark.parametrize("fault", ["old", "nonce", "source", "phase", "schema", "success",
    "duplicate", "partial", "garbage", "large_report", "large_detail", "nested"])
def test_unbound_or_invalid_stderr_never_replaces_failure_or_reads_more(fault):
    value = guest_failure()
    if fault == "old": value.pop("nonce")
    elif fault == "nonce": value["nonce"] = "0" * 64
    elif fault == "source": value["source_binding_sha256"] = "0" * 64
    elif fault == "phase": value["phase"] = "post"
    elif fault == "schema": value["schema"] = "lhq-journal-growth-guest/v2"
    elif fault == "success": value["status"] = "GUEST_QUIET"
    elif fault == "large_report": value["diagnostic"]["runtime_preparation"] = "x" * 32768
    elif fault == "large_detail": value["diagnostic"]["context"] = "x" * 4096
    raw = h.canonical(value)
    if fault == "duplicate": raw = raw[:-2] + b',"status":"INCOMPLETE"}\n'
    elif fault == "partial": raw = raw[:-2]
    elif fault == "garbage": raw = b"unstructured ssh error\n"
    elif fault == "nested": raw = b"[" * 2000 + b"0" + b"]" * 2000
    transport = object.__new__(h.MaintenanceTransport)
    transport.output = dict(stdout=bytearray(), stderr=bytearray(raw))
    transport.eof = dict(stdout=True, stderr=False)
    transport.phase, transport.nonce, transport.source_sha = "pre", NONCE, SHA
    transport.report = None
    transport.pump = lambda: pytest.fail("no read or wait after stdout EOF")
    with pytest.raises(h.prior.r.ObservationError, match="GROWTH_REPORT_MISSING") as caught:
        transport.receive_report()
    assert caught.value.diagnostic == dict(operation="receive_report", phase="pre",
        stderr=dict(bytes=len(raw), sha256=h.digest(raw), eof=False))
    assert transport.report is None


def test_coordinator_receipt_retains_guest_failure_without_later_effects(rig, monkeypatch, local_inventory):
    inv, root, _calls, _reads = local_inventory
    target = root / "evidence" / "receipt"
    target.write_bytes(b"retained evidence"); target.chmod(0o620)
    with pytest.raises(g.r.ObservationError) as caught:
        inv.persistent()
    value = maintenance(inv).failure(caught.value)
    assert value["diagnostic"]["path_lookup"]["qualification"]["mode"] & 0o020
    detail = dict(operation="receive_report", phase="pre", guest_failure={
        key: value[key] for key in ("stage", "reason", "diagnostic")})
    def fail(_):
        error = h.prior.r.ObservationError("GROWTH_REPORT_MISSING")
        error.diagnostic = detail
        raise error
    monkeypatch.setattr(h.MaintenanceTransport, "receive_report", fail)
    result = rig.work.run(rig.manifest)
    assert result["state"] == "STOP_AND_RETAIN" and result["diagnostic"] == detail
    assert rig.actions == ["marker", "pre_ssh"]
    assert h.prior.r.parse(rig.files["receipt.json"], 65536)["diagnostic"] == detail
