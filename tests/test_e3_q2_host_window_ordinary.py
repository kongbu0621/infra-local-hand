"""Independent v2 ordinary-writer boundaries and real local syscall checks.

Successful syscall cases use actual ordinary credentials. Only readiness,
kernel boot and ext4 qualification are explicit models; they do not establish
field readiness, storage durability, remote execution or Q2 acceptance.
"""
import copy
import errno
import multiprocessing
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Ordinary writer uses Linux credentials, procfs and protected fds", allow_module_level=True)

from e3_host import q2_host_window_billing as billing
from e3_host import q2_host_window_contract as c
from e3_host import q2_host_window_record as r
from e3_host import q2_reconciliation_delivery as delivery
from e3_host import q2_reconciliation_io as io


BOOT = "00000000-0000-0000-0000-000000000001"
PARENT_ENV = "LOCAL_HAND_Q2_TEST_PARENT"
OPERATOR_SCHEMA = "local-hand-q2-host-window-operator/v1"
PRECHECK_SCHEMA = "local-hand-q2-host-window-precheck/v2"
INTENT_SCHEMA = "local-hand-q2-host-window-intent/v2"
EVIDENCE_SCHEMA = "local-hand-q2-host-window-consumption/v2"


def operator(uid=1000, gid=1000):
    """Pure declaration, never installed as credentials in a success test."""
    return dict(schema=OPERATOR_SCHEMA, uid=[uid] * 3, gid=[gid] * 3, groups=[10, gid])


def location(parent):
    return dict(schema=c.SOURCES_SCHEMA, parent=str(parent),
        directory=str(parent) + "/" + c.DIRECTORY_NAME, expected_boot_id=BOOT,
        startup_closure=c.STARTUP_AUTHORITY["closure"], carrier_sha256=c.CARRIER_SHA256,
        carrier_bytes=c.CARRIER_BYTES, host_attestation_sha256=c.ATTESTATION_SHA256,
        host_attestation_bytes=c.ATTESTATION_BYTES)


def binding(loc):
    return c.make_binding(implementation_commit="a" * 40, source_tree="b" * 40,
        source_files_sha256="c" * 64, attempt_id="ordinary-model-only-20260929",
        plan_sha256="d" * 64, amendment_sha256="e" * 64,
        configuration_sha256="f" * 64, wrapper_sha256="1" * 64, location=loc)


def host_bill(root, device, scan):
    history = str(root) + "/history"
    declarations = [dict(id=identity, kind=kind, category="capture", commitment=amount,
        covered_paths=[str(root) + "/" + relative], devices=[device], evidence_sha256="3" * 64)
        for identity, kind, relative, amount in (
            ("history", "historical", "history", dict(bytes=16384, inodes=8)),
            ("capture", "capture", "future-capture", dict(bytes=8 * 1024**2, inodes=64)),
            ("host-window-marker", "marker", c.DIRECTORY_NAME, dict(bytes=65536, inodes=4)))]
    return billing.quote_host(dict(host_id=c.ATTESTATION_SHA256, guest_id="4" * 64,
        scans={history: scan}, expected_roots={history: "capture"},
        devices=[dict(device=device, available_bytes=1024**3, free_inodes=100000)],
        obligations=declarations,
        marker=dict(path=str(root) + "/" + c.DIRECTORY_NAME, device=device, state="ABSENT"),
        early_audit=dict(evidence_sha256="5" * 64, host_obligation_ids=[],
            guest_obligation_id="new-owner-pool", guest_reserved=dict(bytes=65536, inodes=4)),
        coverage_sha256="6" * 64))


def fs_model(meta):
    return dict(schema=r.FILESYSTEM_SCHEMA, device=meta["device"], mount_id=1,
        mountpoint="/", source="/dev/synthetic-only", mountinfo_sha256="1" * 64,
        superblock_sha256="2" * 64, block_size=4096, cluster_size=4096,
        parent_flags=r.FS_EXTENTS_FL, parent_size=meta["size"],
        available_bytes=1024**3, free_inodes=100000, allocation_bound=65536,
        logical_bound=16384, inode_bound=4)


def pure_intent():
    root = "/synthetic-ordinary-host"
    loc, who = location(root), operator()
    meta = dict(device=1, inode=10, st_mode=stat.S_IFDIR | 0o700,
        uid=1000, gid=1000, nlink=2, size=4096, blocks=8,
        atime_ns=1, mtime_ns=1, ctime_ns=1)
    history = root + "/history"
    scan = dict(path=history, device=1, bytes=4096, inodes=1, logical_bytes=0,
        entries=[dict(relative_path=".", type="directory", source_metadata=dict(meta, inode=20))])
    bill = host_bill(root, 1, scan)
    window = dict(issued_ns=1, deadline_ns=300 * c.NS + 1,
        boottime_issued_ns=1, boottime_deadline_ns=300 * c.NS + 1)
    proof = dict(schema=PRECHECK_SCHEMA, operator=who,
        location_sha256=c.sha(c.encoded(loc)), window=window, boot_id=BOOT,
        parent_metadata=meta, filesystem=fs_model(meta),
        host_bill_sha256=c.sha(c.encoded(bill)), host_bill_summary=bill["summary"], limits=dict(c.RESERVATION))
    intent = dict(schema=INTENT_SCHEMA, operator=copy.deepcopy(who), scope=c.SCOPE,
        binding=binding(loc), window=window,
        directory_identity=dict(device=1, inode=30, uid=1000, gid=1000, mode=0o700),
        precheck=proof, precheck_sha256=c.sha(c.encoded(proof)), reservation=dict(c.RESERVATION),
        window_consumed=True, owner_issued=False, run_permission="existing_startup_once")
    return intent, loc


def test_operator_complete_identity_is_copied_without_truncation():
    value = operator()
    value["groups"] = list(range(3000))
    checked = c.validate_operator(value)
    assert checked == value and checked is not value
    value["groups"].append(3000)
    assert len(checked["groups"]) == 3000


def test_operator_preserves_complete_sorted_duplicate_groups():
    value = operator(); value["groups"] = [10, 10, 1000]
    assert c.validate_operator(value)["groups"] == [10, 10, 1000]


@pytest.mark.parametrize("field,value", [
    ("schema", "caller-identity"), ("unknown", False),
    ("uid", [0, 0, 0]), ("gid", [0, 0, 0]),
    ("uid", [1000, 0, 1000]), ("uid", [1000, 1000, 0]),
    ("gid", [1000, 1001, 1000]), ("gid", [1000, 1000, 1001]),
    ("uid", [True] * 3), ("gid", [-1] * 3), ("uid", [2**32 - 1] * 3),
    ("uid", [1000, 1000]), ("gid", (1000, 1000, 1000)),
    ("groups", [1000, 10]), ("groups", [True]), ("groups", [-1]),
    ("groups", [2**32 - 1]), ("groups", tuple()), ("groups", list(range(65537))),
])
def test_operator_rejects_ambiguous_or_unbounded_identity(field, value):
    data = operator(); data[field] = value
    with pytest.raises(ValueError):
        c.validate_operator(data)


def test_v2_pure_intent_is_bound_and_v1_decoder_refuses_it():
    value, loc = pure_intent()
    assert r.validate_precheck_ordinary(value["precheck"], loc, value["window"]) == value["precheck"]
    assert c.verify_intent_ordinary(c.encoded(value), value["binding"], loc) == value
    with pytest.raises(ValueError):
        c.verify_intent(c.encoded(value), value["binding"], loc)
    with pytest.raises(ValueError):
        r.validate_precheck(value["precheck"], loc, value["window"])


@pytest.mark.parametrize("change", [
    lambda v: v.update(unknown=True),
    lambda v: v.update(schema=c.INTENT_SCHEMA),
    lambda v: v["precheck"].update(unknown=True),
    lambda v: v["operator"].update(uid=[1001] * 3),
    lambda v: v["precheck"]["parent_metadata"].update(uid=1001),
    lambda v: v["precheck"]["parent_metadata"].update(gid=1001),
    lambda v: v["directory_identity"].update(uid=1001),
    lambda v: v["directory_identity"].update(gid=1001),
    lambda v: v["directory_identity"].update(inode=10),
    lambda v: v["reservation"].update(bytes=65537),
    lambda v: v["precheck"]["limits"].update(inodes=5),
    lambda v: v["precheck"]["filesystem"].update(logical_bound=16385),
    lambda v: v["precheck"]["filesystem"].update(allocation_bound=65537),
    lambda v: v.update(window_consumed=False),
])
def test_recomputed_digest_cannot_launder_identity_budget_or_schema(change):
    value, loc = pure_intent(); change(value)
    value["precheck_sha256"] = c.sha(c.encoded(value["precheck"]))
    with pytest.raises(ValueError):
        c.verify_intent_ordinary(c.encoded(value), value["binding"], loc)


def test_full_operator_width_must_fit_original_intent_budget():
    value, loc = pure_intent()
    # Legal complete identity width may exceed this operation's unchanged
    # encoding budget. It must block instead of truncating supplementary groups.
    value["operator"]["groups"] = list(range(4000))
    value["precheck"]["operator"] = copy.deepcopy(value["operator"])
    assert c.validate_operator(value["operator"]) == value["operator"]
    value["precheck_sha256"] = c.sha(c.encoded(value["precheck"]))
    with pytest.raises(ValueError):
        c.verify_intent_ordinary(c.encoded(value), value["binding"], loc)


@pytest.mark.parametrize("field", ["uid", "gid", "groups"])
def test_counterfactual_identity_change_during_capture_is_rejected(monkeypatch, field):
    """Pure negative sampling model; never reported as ordinary execution."""
    reads = {"uid": 0, "gid": 0, "groups": 0}
    def sampled(name):
        reads[name] += 1
        shifted = 1 if name == field and reads[name] > 1 else 0
        return [1000 + shifted] if name == "groups" else (1000 + shifted,) * 3
    monkeypatch.setattr(r.os, "getresuid", lambda: sampled("uid"))
    monkeypatch.setattr(r.os, "getresgid", lambda: sampled("gid"))
    monkeypatch.setattr(r.os, "getgroups", lambda: sampled("groups"))
    with pytest.raises(ValueError, match="IDENTITY|OPERATOR"):
        r._current_operator()


@pytest.fixture
def ordinary():
    # No credential changes or fake successful identities. CI supplies the
    # already prepared ordinary-owned directory below protected root ancestry.
    supplied = os.environ.get(PARENT_ENV)
    uid, gid = os.getresuid(), os.getresgid()
    if uid[0] == 0 or gid[0] == 0:
        if supplied is not None:
            pytest.fail("Configured ordinary writer fixture requires actual nonroot credentials")
        pytest.skip("Actual ordinary credentials unavailable; no ordinary-writer success claimed")
    assert len(set(uid)) == len(set(gid)) == 1
    parent = Path(supplied) if supplied is not None else Path.home()
    assert parent.is_absolute() and str(parent) == os.path.abspath(parent)
    initial = dict(schema=OPERATOR_SCHEMA, uid=list(uid), gid=list(gid), groups=sorted(os.getgroups()))
    assert c.validate_operator(initial) == initial
    # Qualification is real and does not repair existing ancestor permissions.
    with io.HeldPath(str(parent), lambda: None, directory=True, allowed_uids={0, uid[0]}) as held:
        assert os.fstat(held.fd).st_uid == uid[0]
    with tempfile.TemporaryDirectory(prefix="q2-ordinary-writer-", dir=parent) as name:
        root = Path(name); history = root / "history"
        history.mkdir(mode=0o700)
        old = history / "old"
        old.write_bytes(b"unchanged isolated history\n"); old.chmod(0o400)
        loc, window = location(root), delivery.Window()
        bill = host_bill(root, root.stat().st_dev,
            io.snapshot(history, window.guard, allowed_uids={0, uid[0]}))
        handles = []
        data = SimpleNamespace(root=root, old=old, location=loc, binding=binding(loc),
            window=window, bill=bill, identity=initial, handles=handles)
        def precheck():
            pre = r.precheck_ordinary(loc, data.binding, data.window, data.bill)
            handles.append(pre); return pre
        def consume():
            result = precheck().consume(); handles.append(result); return result
        data.precheck, data.consume = precheck, consume
        try:
            yield data
        finally:
            for handle in reversed(handles):
                handle.close()


@pytest.fixture
def modeled(ordinary, monkeypatch):
    """Only these three field prerequisites are modeled in syscall successes."""
    monkeypatch.setattr(r.c, "require_field_readiness", lambda value: None)
    def boot(guard):
        guard(); return BOOT
    def filesystem(parent, guard):
        guard(); return fs_model(io.metadata(os.fstat(parent.fd)))
    monkeypatch.setattr(r, "_boot", boot)
    monkeypatch.setattr(r, "filesystem", filesystem)
    return ordinary


def test_production_readiness_refuses_before_any_identity_or_file_access(monkeypatch):
    value, loc = pure_intent()
    def forbidden(*args, **kwargs):
        pytest.fail("field access before readiness")
    monkeypatch.setattr(r.os, "open", forbidden)
    monkeypatch.setattr(r.os, "mkdir", forbidden)
    monkeypatch.setattr(r.os, "getresuid", forbidden)
    with pytest.raises(ValueError, match="FIELD_READINESS_UNPROVEN"):
        r.precheck_ordinary(loc, value["binding"], delivery.Window(), {})


def test_real_ordinary_creation_fsync_readback_noatime_and_acl(modeled, monkeypatch):
    real_open, real_sync, real_acl = os.open, os.fsync, os.getxattr
    real_close, real_read, real_listdir, real_scandir = os.close, os.read, os.listdir, os.scandir
    opened, synced, acl = [], [], []
    metadata_only = set()
    def tracked_open(name, flags, *args, **kwargs):
        fd = real_open(name, flags, *args, **kwargs)
        opened.append((name, flags))
        if name == "." and not flags & os.O_NOATIME:
            metadata_only.add(fd)
        return fd
    def tracked_close(fd):
        metadata_only.discard(fd); return real_close(fd)
    def tracked_read(fd, length):
        assert fd not in metadata_only, "ancestor ACL descriptor must not read content"
        return real_read(fd, length)
    def listing(original):
        def checked(path="."):
            assert not isinstance(path, int) or path not in metadata_only, "ancestor ACL descriptor must not enumerate"
            return original(path)
        return checked
    def tracked_sync(fd):
        synced.append(stat.S_ISDIR(os.fstat(fd).st_mode)); return real_sync(fd)
    def tracked_acl(fd, name, *args, **kwargs):
        before = io.metadata(os.fstat(fd))
        acl.append((before["inode"], name))
        try:
            return real_acl(fd, name, *args, **kwargs)
        finally:
            assert io.metadata(os.fstat(fd)) == before
    monkeypatch.setattr(r.os, "open", tracked_open)
    monkeypatch.setattr(r.os, "close", tracked_close)
    monkeypatch.setattr(r.os, "read", tracked_read)
    monkeypatch.setattr(r.os, "listdir", listing(real_listdir))
    monkeypatch.setattr(r.os, "scandir", listing(real_scandir))
    monkeypatch.setattr(r.os, "fsync", tracked_sync)
    monkeypatch.setattr(r.os, "getxattr", tracked_acl)
    old_before = io.metadata(modeled.old.stat())
    held = modeled.consume()
    intent = c.document(held.intent_raw)
    assert intent["schema"] == INTENT_SCHEMA and intent["operator"] == modeled.identity
    assert intent["precheck"]["operator"] == modeled.identity
    assert held.evidence["schema"] == EVIDENCE_SCHEMA and held.evidence["allow_run"] is False
    assert len(synced) >= 5 and False in synced
    assert {name for _, name in acl} == {"system.posix_acl_access", "system.posix_acl_default"}
    for _, _, meta in held.parent.chain:
        assert (meta["inode"], "system.posix_acl_access") in acl
        assert (meta["inode"], "system.posix_acl_default") in acl
    assert any(name == "." and not flags & os.O_NOATIME for name, flags in opened)
    assert all(flags & os.O_NOATIME for name, flags in opened
        if not flags & os.O_PATH and name != ".")
    path = Path(modeled.location["directory"]) / c.INTENT_NAME
    before = io.metadata(path.stat())
    assert before["uid"] == modeled.identity["uid"][0] and before["gid"] == modeled.identity["gid"][0]
    assert stat.S_IMODE(before["st_mode"]) == 0o400
    held.verify(); held.verify()
    assert not metadata_only
    assert io.metadata(path.stat()) == before
    assert io.metadata(modeled.old.stat()) == old_before
    report = r.verify_existing_ordinary(modeled.location, modeled.binding, modeled.window, held.intent_sha256)
    assert report["status"] == "CONSUMED_READ_ONLY" and report["allow_run"] is False
    assert report["reader_operator"] == modeled.identity
    assert io.metadata(path.stat()) == before
    with pytest.raises(ValueError):
        r.verify_existing(modeled.location, modeled.binding, modeled.window, held.intent_sha256)
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        modeled.precheck()


@pytest.mark.parametrize("acl_value", [b"modeled extended ACL", OSError(errno.EOPNOTSUPP, "ACL unknown")])
def test_acl_present_or_unknown_is_rejected_before_creation(modeled, monkeypatch, acl_value):
    def acl(*args):
        if isinstance(acl_value, OSError):
            raise acl_value
        return acl_value
    monkeypatch.setattr(r.os, "getxattr", acl)
    with pytest.raises(ValueError, match="ACL_"):
        modeled.precheck()
    assert not Path(modeled.location["directory"]).exists()


def test_noatime_denial_has_no_weaker_open_fallback(modeled, monkeypatch):
    real_open, denied = os.open, []
    def open_file(name, flags, *args, **kwargs):
        if name == modeled.root.name:
            denied.append(flags)
            if flags & os.O_NOATIME:
                raise PermissionError(errno.EPERM, "model noatime denial")
        return real_open(name, flags, *args, **kwargs)
    monkeypatch.setattr(r.os, "open", open_file)
    with pytest.raises(PermissionError):
        modeled.precheck()
    assert denied and all(flags & os.O_NOATIME for flags in denied)
    assert not Path(modeled.location["directory"]).exists()


@pytest.mark.parametrize("failure", ["fsync", "short-write"])
def test_failed_creation_retains_partial_and_prevents_replay(modeled, monkeypatch, failure):
    pre = modeled.precheck()
    with monkeypatch.context() as patcher:
        if failure == "fsync":
            def failed(fd):
                raise OSError(errno.EIO, "modeled fsync failure")
            patcher.setattr(r.os, "fsync", failed)
            expected = OSError
        else:
            real_write = os.write
            patcher.setattr(r.os, "write", lambda fd, raw: real_write(fd, raw[:9]))
            expected = ValueError
        with pytest.raises(expected):
            pre.consume()
    marker = Path(modeled.location["directory"])
    assert marker.is_dir()
    if failure == "short-write":
        assert (marker / c.INTENT_NAME).stat().st_size == 9
    else:
        assert list(marker.iterdir()) == []
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        modeled.precheck()


@pytest.mark.parametrize("getter", ["getresuid", "getresgid", "getgroups"])
def test_counterfactual_identity_drift_refuses_before_read_or_write(modeled, monkeypatch, getter):
    # Success up to this point used real credentials; only the subsequent
    # credential-change event is modeled, without claiming real setuid success.
    pre = modeled.precheck()
    prior = getattr(os, getter)()
    changed = sorted([*prior, max(prior, default=1000) + 1]) if getter == "getgroups" else tuple(x + 1 for x in prior)
    with monkeypatch.context() as patcher:
        patcher.setattr(r.os, getter, lambda: changed)
        patcher.setattr(r.os, "open", lambda *a, **kw: pytest.fail("read after identity drift"))
        patcher.setattr(r.os, "mkdir", lambda *a, **kw: pytest.fail("write after identity drift"))
        with pytest.raises(ValueError, match="IDENTITY|OPERATOR"):
            pre.consume()
    assert not Path(modeled.location["directory"]).exists()


def test_counterfactual_saved_id_change_blocks_retained_read(modeled, monkeypatch):
    held = modeled.consume(); original = os.getresuid()
    monkeypatch.setattr(r.os, "getresuid", lambda: (original[0], original[1], original[2] + 1))
    monkeypatch.setattr(r.os, "open", lambda *a, **kw: pytest.fail("open after saved identity drift"))
    monkeypatch.setattr(r.os, "read", lambda *a, **kw: pytest.fail("payload read after saved identity drift"))
    with pytest.raises(ValueError, match="IDENTITY|OPERATOR"):
        held.verify()


@pytest.mark.parametrize("stage", ["mkdir", "intent-open"])
def test_counterfactual_postcreate_drift_retains_partial_without_more_io(modeled, monkeypatch, stage):
    pre = modeled.precheck()
    real_open, real_mkdir = os.open, os.mkdir
    original = os.getgroups()
    changed_groups = sorted([*original, max(original, default=1000) + 1])
    changed = [False]
    def mkdir(*args, **kwargs):
        result = real_mkdir(*args, **kwargs)
        if stage == "mkdir": changed[0] = True
        return result
    def opened(name, *args, **kwargs):
        assert not changed[0], "open after captured operator changed"
        fd = real_open(name, *args, **kwargs)
        if stage == "intent-open" and name == c.INTENT_NAME: changed[0] = True
        return fd
    with monkeypatch.context() as patcher:
        patcher.setattr(r.os, "getgroups", lambda: changed_groups if changed[0] else original)
        patcher.setattr(r.os, "mkdir", mkdir)
        patcher.setattr(r.os, "open", opened)
        patcher.setattr(r.os, "write", lambda *args: pytest.fail("payload after operator drift"))
        with pytest.raises(ValueError, match="IDENTITY|OPERATOR"):
            pre.consume()
    marker = Path(modeled.location["directory"])
    assert marker.is_dir()
    if stage == "mkdir":
        assert list(marker.iterdir()) == []
    else:
        assert (marker / c.INTENT_NAME).stat().st_size == 0
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        modeled.precheck()


def test_file_owner_mismatch_is_rejected_before_payload_write(modeled, monkeypatch):
    pre = modeled.precheck(); real_open, real_fstat = os.open, os.fstat
    payload_fds = set()
    def opened(name, flags, *args, **kwargs):
        fd = real_open(name, flags, *args, **kwargs)
        if name == c.INTENT_NAME:
            payload_fds.add(fd)
        return fd
    def mismatched(fd):
        info = real_fstat(fd)
        if fd not in payload_fds:
            return info
        # A metadata substitution fault, not a real chown or ordinary identity.
        values = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
        values["st_uid"] = modeled.identity["uid"][0] + 1
        return SimpleNamespace(**values)
    with monkeypatch.context() as patcher:
        patcher.setattr(r.os, "open", opened)
        patcher.setattr(r.os, "fstat", mismatched)
        patcher.setattr(r.os, "write", lambda *a: pytest.fail("payload write to foreign owner"))
        with pytest.raises(ValueError, match="IDENTITY|OWNER"):
            pre.consume()
    intent = Path(modeled.location["directory"]) / c.INTENT_NAME
    assert intent.is_file() and intent.stat().st_size == 0


@pytest.mark.parametrize("object_kind", ["directory", "intent"])
def test_acl_stage_name_replacement_refuses_before_payload(modeled, monkeypatch, object_kind):
    """Real rename/replacement under actual ordinary credentials, not fake fds."""
    pre = modeled.precheck()
    marker = Path(modeled.location["directory"])
    target = marker if object_kind == "directory" else marker / c.INTENT_NAME
    retained = modeled.root / "retained-marker" if object_kind == "directory" else marker / "retained-intent"
    real_acl = os.getxattr
    replaced = []
    def acl_then_replace(fd, name, *args, **kwargs):
        if not replaced and target.exists() and os.fstat(fd).st_ino == target.stat().st_ino:
            target.rename(retained)
            if object_kind == "directory":
                target.mkdir(mode=0o700)
            else:
                target.touch(mode=0o400)
            replaced.append(True)
        return real_acl(fd, name, *args, **kwargs)
    with monkeypatch.context() as patcher:
        patcher.setattr(r.os, "getxattr", acl_then_replace)
        patcher.setattr(r.os, "write", lambda *args: pytest.fail("payload after name replacement"))
        with pytest.raises(ValueError, match="CHANGED|REPLACED|IDENTITY"):
            pre.consume()
    assert replaced and retained.exists() and target.exists()
    if object_kind == "intent":
        assert target.stat().st_size == retained.stat().st_size == 0
    else:
        assert all(path.stat().st_size == 0 for path in retained.iterdir() if path.is_file())
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        modeled.precheck()


@pytest.mark.parametrize("victim_kind", ["ancestor", "parent"])
def test_later_acl_stage_ancestor_replacement_blocks_stale_fd_writes(modeled, monkeypatch, victim_kind):
    """Replace only new isolated ancestry, after the original precheck passes."""
    outer = modeled.root / "isolated-ancestor"
    outer.mkdir(mode=0o700)
    parent = outer / "parent"; parent.mkdir(mode=0o700)
    history = parent / "history"; history.mkdir(mode=0o700)
    (history / "old").write_bytes(b"isolated ancestor race history\n")
    (history / "old").chmod(0o400)
    loc = location(parent)
    bill = host_bill(parent, parent.stat().st_dev,
        io.snapshot(history, modeled.window.guard, allowed_uids={0, os.geteuid()}))
    pre = r.precheck_ordinary(loc, binding(loc), modeled.window, bill)
    modeled.handles.append(pre)
    parent_inode = parent.stat().st_ino
    victim = outer if victim_kind == "ancestor" else parent
    retained = victim.with_name(victim.name + "-retained")
    real_acl, real_mkdir = os.getxattr, os.mkdir
    replaced, marker_creations = [], []

    def acl_then_replace(fd, name, *args, **kwargs):
        info = os.fstat(fd)
        # Ancestor was checked earlier in this ACL walk; replace it while
        # checking its descendant parent. The parent case waits until the new
        # intent's ACL, after that parent's earlier validation has completed.
        trigger = (info.st_ino == parent_inode and name == "system.posix_acl_default"
            if victim_kind == "ancestor" else stat.S_ISREG(info.st_mode) and info.st_size == 0)
        if not replaced and trigger:
            victim.rename(retained)
            victim.mkdir(mode=0o700)
            replaced.append(True)
        return real_acl(fd, name, *args, **kwargs)

    def mkdir(name, *args, **kwargs):
        if name == c.DIRECTORY_NAME:
            assert not replaced, "marker mkdir through displaced ancestor fd"
            marker_creations.append(True)
        return real_mkdir(name, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(r.os, "getxattr", acl_then_replace)
        patcher.setattr(r.os, "mkdir", mkdir)
        patcher.setattr(r.os, "write", lambda *args: pytest.fail("payload through displaced parent fd"))
        with pytest.raises(ValueError, match="CHANGED|REPLACED|IDENTITY"):
            pre.consume()
    assert replaced and victim.is_dir() and retained.is_dir()
    if victim_kind == "ancestor":
        assert marker_creations == []
        assert not (retained / "parent" / c.DIRECTORY_NAME).exists()
    else:
        assert marker_creations == [True]
        assert (retained / c.DIRECTORY_NAME / c.INTENT_NAME).stat().st_size == 0
        assert not (parent / c.DIRECTORY_NAME).exists()


def test_historical_parent_inode_cannot_be_laundered_with_matching_hash(modeled):
    held = modeled.consume()
    value = c.document(held.intent_raw)
    value["precheck"]["parent_metadata"]["inode"] += 100000
    value["precheck_sha256"] = c.sha(c.encoded(value["precheck"]))
    forged = c.encoded(value)
    # Caller knows the replacement digest, but cannot replace the inode which
    # the v2 precheck bound. Replace only this new isolated intent test file.
    replacement = modeled.root / "forged-intent"
    replacement.write_bytes(forged); replacement.chmod(0o400)
    os.replace(replacement, Path(modeled.location["directory"]) / c.INTENT_NAME)
    with pytest.raises(ValueError, match="PARENT|CHANGED"):
        r.verify_existing_ordinary(modeled.location, modeled.binding, modeled.window, c.sha(forged))


def test_current_reader_and_historical_issuer_groups_are_separate(modeled):
    held = modeled.consume()
    value = c.document(held.intent_raw)
    current = modeled.identity["groups"]
    historical = sorted([*current, max(current, default=1000) + 1])
    # Construct an explicitly modeled historical group observation in this
    # isolated record. Current reader credentials remain entirely unpatched.
    value["operator"]["groups"] = historical
    value["precheck"]["operator"]["groups"] = historical
    value["precheck_sha256"] = c.sha(c.encoded(value["precheck"]))
    raw = c.encoded(value)
    replacement = modeled.root / "historical-group-intent"
    replacement.write_bytes(raw); replacement.chmod(0o400)
    os.replace(replacement, Path(modeled.location["directory"]) / c.INTENT_NAME)
    report = r.verify_existing_ordinary(modeled.location, modeled.binding, modeled.window, c.sha(raw))
    assert report["intent"]["operator"]["groups"] == historical
    assert report["reader_operator"] == modeled.identity
    assert report["allow_run"] is False


def test_two_real_ordinary_processes_compete_for_single_receipt(modeled):
    ctx = multiprocessing.get_context("fork")
    ready, outcomes = ctx.Barrier(2), ctx.Queue()
    def contender():
        pre = held = None
        try:
            assert os.getresuid() == tuple(modeled.identity["uid"])
            pre = r.precheck_ordinary(modeled.location, modeled.binding, modeled.window, modeled.bill)
            ready.wait(timeout=10)
            held = pre.consume()
            outcomes.put((True, held.intent_sha256))
        except BaseException as error:
            outcomes.put((False, type(error).__name__ + ":" + str(error)))
        finally:
            if held is not None: held.close()
            if pre is not None: pre.close()
    processes = [ctx.Process(target=contender) for _ in range(2)]
    try:
        for child in processes: child.start()
        for child in processes:
            child.join(timeout=15)
            assert not child.is_alive() and child.exitcode == 0
        rows = [outcomes.get(timeout=3) for _ in processes]
        assert sum(success for success, _ in rows) == 1, rows
        assert any(not success and ("ALREADY_CONSUMED" in text or "CHANGED" in text) for success, text in rows), rows
        assert (Path(modeled.location["directory"]) / c.INTENT_NAME).is_file()
    finally:
        for child in processes:
            if child.is_alive(): child.kill()
            if child.pid is not None: child.join(timeout=3)
        outcomes.close(); outcomes.join_thread()
