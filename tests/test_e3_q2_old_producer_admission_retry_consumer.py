"""Isolation tests for the two-read old-producer kernel consumer."""
from __future__ import annotations

import ast
import copy
import inspect
from pathlib import Path
import sys

import pytest

from e3_host import q2_old_producer_admission_retry_consumer as m


pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"),
    reason="Old-producer identity and fixed kernel readers are Linux-only")


D = "a" * 40
TREE = "b" * 40
BOOT = "11111111-2222-3333-4444-555555555555"
MOUNTINFO = (
    b"10 1 8:1 / / rw,relatime - ext4 /dev/root rw\n"
    b"11 10 8:2 /data /private rw - ext4 /dev/data rw\n"
    b"12 11 8:2 /consumption /private/consumption-parent rw - ext4 /dev/data rw\n"
)


def parent(path, *, device, inode):
    return dict(schema=m.contract.PARENT_SCHEMA, path=path, type="directory",
        uid=1000, gid=1000, mode=0o755, device=device, inode=inode)


def package():
    c = m.contract
    locator = c.encoded(dict(schema=c.LOCATOR_SCHEMA,
        parent=parent("/private/consumption-parent", device=10, inode=20)))
    context = c.encoded(dict(schema=c.CONTEXT_SCHEMA,
        locator_sha256=c.sha(locator), expected_host_boot_id=BOOT,
        operator=dict(schema=c.OPERATOR_SCHEMA, uid=[1000, 1000, 1000],
            gid=[1000, 1000, 1000], groups=[4, 1000, 1000]),
        ssh_identity_sha256="c" * 64, guest_identity_sha256="d" * 64,
        evidence_parent=parent("/private/evidence-parent", device=11, inode=21)))
    evidence = dict(basename="local-hand-20261002a-evidence.zip",
        evidence_max_frame_bytes=1049600,
        evidence_max_archive_logical_bytes=1048576,
        evidence_max_archive_allocated_bytes=2097152,
        evidence_archive_inode_count=1)
    manifest = c.make_manifest(implementation_commit=D, implementation_tree=TREE,
        locator_raw=locator, context_raw=context, evidence=evidence)
    return c.encoded(manifest), locator, context


def observe(manifest, locator, context, *, implementation_commit=D,
            implementation_tree=TREE):
    return m.observe(manifest, locator, context,
        implementation_commit=implementation_commit,
        implementation_tree=implementation_tree)


def stable_identity(monkeypatch, *, uid=(1000, 1000, 1000),
                    gid=(1000, 1000, 1000), groups=(1000, 4, 1000)):
    monkeypatch.setattr(m.os, "getresuid", lambda: uid)
    monkeypatch.setattr(m.os, "getresgid", lambda: gid)
    monkeypatch.setattr(m.os, "getgroups", lambda: list(groups))


def clocks(monkeypatch):
    events = []
    values = {"boot": 10 * m.NS, "mono": 20 * m.NS}

    def boot(clock):
        assert clock == m.time.CLOCK_BOOTTIME
        events.append("boot")
        values["boot"] += 1000
        return values["boot"]

    def mono():
        events.append("mono")
        values["mono"] += 1000
        return values["mono"]

    monkeypatch.setattr(m.time, "clock_gettime_ns", boot)
    monkeypatch.setattr(m.time, "monotonic_ns", mono)
    return events


def successful_reader(monkeypatch, calls, *, mountinfo=MOUNTINFO):
    def read_fact(kind, guard, report):
        calls.append(kind)
        guard()
        guard()
        report.update(status="OBSERVED", target=kind,
            maximum_bytes=64 if kind == "boot" else 1024**2,
            qualification={"content_open_noatime": False})
        return (BOOT + "\n").encode() if kind == "boot" else mountinfo
    monkeypatch.setattr(m.kernel, "read_fact", read_fact)


def test_exact_package_binding_identity_and_two_fixed_reads(monkeypatch):
    manifest, locator, context = package()
    stable_identity(monkeypatch)
    events, calls = clocks(monkeypatch), []
    successful_reader(monkeypatch, calls)

    result = observe(manifest, locator, context)

    assert calls == ["boot", "mountinfo"]
    assert events[:4] == ["boot", "mono", "mono", "boot"]
    assert result["package_binding"] == {
        "manifest_sha256": m.contract.sha(manifest),
        "locator_sha256": m.contract.sha(locator),
        "context_sha256": m.contract.sha(context),
    }
    assert result["parents"]["consumption"]["containing_mount"]["mount_id"] == 12
    assert result["parents"]["evidence"]["containing_mount"]["mount_id"] == 11
    assert result["parents"]["consumption"]["filesystem_qualified"] is False
    assert result["namespace_alignment"]["status"] == "EXTERNAL_ASSUMPTION_NOT_PROVEN"
    assert all(result[name] is False for name in
        ("field_ready", "allow_run", "guest_executed", "remote_attempted",
         "host_persistence_attempted"))
    assert result["normal_chain_executions"] == 0


@pytest.mark.parametrize(("uid", "gid", "groups"), [
    ((0, 0, 0), (1000, 1000, 1000), (4, 1000)),
    ((1000, 1001, 1000), (1000, 1000, 1000), (4, 1000)),
    ((1000, 1000, 1000), (1000, 0, 1000), (4, 1000)),
    ((1000, 1000, 1000), (1000, 1000, 1000), (4, 1001)),
])
def test_root_mixed_or_context_mismatched_identity_stops_before_reader(
        monkeypatch, uid, gid, groups):
    manifest, locator, context = package()
    stable_identity(monkeypatch, uid=uid, gid=gid, groups=groups)
    clocks(monkeypatch)
    calls = []
    monkeypatch.setattr(m.kernel, "read_fact",
        lambda *args, **kwargs: calls.append(args[0]))
    with pytest.raises(ValueError):
        observe(manifest, locator, context)
    assert calls == []


def test_package_member_tamper_stops_before_identity_or_reader(monkeypatch):
    manifest, locator, context = package()
    changed = locator.replace(b"/private/consumption-parent",
        b"/private/other-parent")
    clocks(monkeypatch)
    identity_calls, reader_calls = [], []
    monkeypatch.setattr(m, "_current_identity", lambda: identity_calls.append(1))
    monkeypatch.setattr(m.kernel, "read_fact",
        lambda *args, **kwargs: reader_calls.append(args[0]))
    with pytest.raises(ValueError, match="CONTEXT_BINDING|MEMBER_BINDING"):
        observe(manifest, changed, context)
    assert identity_calls == reader_calls == []


@pytest.mark.parametrize(("commit", "tree"), [
    ("e" * 40, TREE),
    (D, "e" * 40),
])
def test_external_implementation_pin_mismatch_stops_before_identity_or_reader(
        monkeypatch, commit, tree):
    manifest, locator, context = package()
    clocks(monkeypatch)
    identity_calls, reader_calls = [], []
    monkeypatch.setattr(m, "_current_identity", lambda: identity_calls.append(1))
    monkeypatch.setattr(m.kernel, "read_fact",
        lambda *args, **kwargs: reader_calls.append(args[0]))
    with pytest.raises(ValueError, match="IMPLEMENTATION"):
        observe(manifest, locator, context, implementation_commit=commit,
            implementation_tree=tree)
    assert identity_calls == reader_calls == []


def test_identity_drift_during_first_reader_stops_without_mountinfo(monkeypatch):
    manifest, locator, context = package()
    clocks(monkeypatch)
    expected = m.contract.validate_context(context, locator)["operator"]
    changed = copy.deepcopy(expected)
    changed["groups"] = [4, 1001]
    values = iter((expected, expected, changed))
    monkeypatch.setattr(m, "_current_identity", lambda: next(values))
    calls = []

    def read_fact(kind, guard, report):
        calls.append(kind)
        guard()
        pytest.fail("reader continued after the changed identity")

    monkeypatch.setattr(m.kernel, "read_fact", read_fact)
    with pytest.raises(ValueError, match="IDENTITY_CHANGED"):
        observe(manifest, locator, context)
    assert calls == ["boot"]


@pytest.mark.parametrize(("drift_call", "expected_reads"), [
    (4, ["boot"]),
    (5, ["boot", "mountinfo"]),
    (6, ["boot", "mountinfo"]),
])
def test_identity_drift_between_or_after_fixed_reads_is_not_accepted(
        monkeypatch, drift_call, expected_reads):
    manifest, locator, context = package()
    clocks(monkeypatch)
    expected = m.contract.validate_context(context, locator)["operator"]
    changed = copy.deepcopy(expected)
    changed["groups"] = [4, 1001]
    identity_calls = 0

    def current_identity():
        nonlocal identity_calls
        identity_calls += 1
        return changed if identity_calls == drift_call else expected

    monkeypatch.setattr(m, "_current_identity", current_identity)
    calls = []

    def read_fact(kind, guard, report):
        calls.append(kind)
        guard()
        return (BOOT + "\n").encode() if kind == "boot" else MOUNTINFO

    monkeypatch.setattr(m.kernel, "read_fact", read_fact)
    with pytest.raises(ValueError, match="IDENTITY_CHANGED"):
        observe(manifest, locator, context)
    assert calls == expected_reads


@pytest.mark.parametrize(("boot_values", "mono_values", "reason"), [
    ((10 * m.NS, 10 * m.NS - 1), (20 * m.NS, 20 * m.NS + 1),
        "CLOCK_ROLLBACK"),
    ((10 * m.NS, 160 * m.NS), (20 * m.NS, 170 * m.NS),
        "PREPARATION_EXPIRED"),
    ((10 * m.NS, 13 * m.NS), (20 * m.NS, 20 * m.NS),
        "CLOCK_DIVERGED"),
])
def test_window_guard_rejects_rollback_expiry_and_divergence_before_reader(
        monkeypatch, boot_values, mono_values, reason):
    manifest, locator, context = package()
    stable_identity(monkeypatch)
    boot, mono = iter(boot_values), iter(mono_values)
    monkeypatch.setattr(m.time, "clock_gettime_ns", lambda clock: next(boot))
    monkeypatch.setattr(m.time, "monotonic_ns", lambda: next(mono))
    reader_calls = []
    monkeypatch.setattr(m.kernel, "read_fact",
        lambda *args, **kwargs: reader_calls.append(args[0]))
    with pytest.raises(ValueError, match=reason):
        observe(manifest, locator, context)
    assert reader_calls == []


def test_boot_mismatch_stops_before_mountinfo_and_never_falls_back(monkeypatch):
    manifest, locator, context = package()
    stable_identity(monkeypatch)
    clocks(monkeypatch)
    calls = []

    def read_fact(kind, guard, report):
        calls.append(kind)
        guard()
        return b"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\n"

    monkeypatch.setattr(m.kernel, "read_fact", read_fact)
    with pytest.raises(ValueError, match="BOOT_CHANGED"):
        observe(manifest, locator, context)
    assert calls == ["boot"]


def test_reader_error_is_not_downgraded_or_retried(monkeypatch):
    manifest, locator, context = package()
    stable_identity(monkeypatch)
    clocks(monkeypatch)
    calls = []

    def read_fact(kind, guard, report):
        calls.append(kind)
        raise PermissionError("synthetic fixed-reader failure")

    monkeypatch.setattr(m.kernel, "read_fact", read_fact)
    with pytest.raises(PermissionError):
        observe(manifest, locator, context)
    assert calls == ["boot"]


@pytest.mark.parametrize("raw", [
    b"", b"1 0 8:1 / / rw ext4 /dev/root rw\n",
    b"1 0 8:1 / / rw - ext4 /dev/root rw\n1 0 8:1 / /x rw - ext4 /dev/root rw\n",
    b"1 0 8:1 / /bad\\777 rw - ext4 /dev/root rw\n", b"\xff\n",
])
def test_mountinfo_parser_rejects_malformed_or_ambiguous_inputs(raw):
    with pytest.raises(ValueError):
        m.parse_mountinfo(raw)


@pytest.mark.parametrize("namespace", ["cgroup", "ipc", "mnt", "net", "pid",
    "time", "user", "uts"])
def test_namespace_root_is_preserved_only_as_nsfs_root(namespace):
    root = namespace + ":[4026531840]"
    raw = f"13 10 0:4 {root} /run/snapd/ns/example.mnt rw - nsfs nsfs rw\n".encode()

    row, = m.parse_mountinfo(raw)

    assert row["root"] == root
    assert row["mountpoint"] == "/run/snapd/ns/example.mnt"
    assert row["filesystem"] == "nsfs"


def test_unrelated_nsfs_mount_preserves_ext4_parent_observation(monkeypatch):
    manifest, locator, context = package()
    stable_identity(monkeypatch)
    clocks(monkeypatch)
    calls = []
    mountinfo = MOUNTINFO + (
        b"13 10 0:4 mnt:[4026531840] /run/snapd/ns/example.mnt rw - nsfs nsfs rw\n"
    )
    successful_reader(monkeypatch, calls, mountinfo=mountinfo)

    result = observe(manifest, locator, context)

    assert calls == ["boot", "mountinfo"]
    assert {role: value["containing_mount"]["mount_id"]
        for role, value in result["parents"].items()} == {"consumption": 12, "evidence": 11}
    assert all(value["containing_mount"]["filesystem"] == "ext4"
        and value["filesystem_qualified"] is False
        and value["peak_and_persistence_qualified"] is False
        for value in result["parents"].values())
    assert result["status"] == "OBSERVED_NOT_READY"
    assert all(result[name] is False for name in ("field_ready", "allow_run",
        "guest_executed", "remote_attempted", "host_persistence_attempted"))


def test_nsfs_parent_overlay_is_observed_without_ext4_or_readiness_claim(monkeypatch):
    manifest, locator, context = package()
    stable_identity(monkeypatch)
    clocks(monkeypatch)
    calls = []
    mountinfo = MOUNTINFO + (
        b"13 11 0:4 mnt:[4026531840] /private/evidence-parent rw - nsfs nsfs rw\n"
    )
    successful_reader(monkeypatch, calls, mountinfo=mountinfo)
    # Mount selection must retain namespace mounts. Dropping them would hide
    # a more specific containing mount from future filesystem qualification.
    rows = m.parse_mountinfo(mountinfo)
    selected = m._containing_mount(rows, "/private/evidence-parent/child")
    assert selected["mount_id"] == 13
    assert selected["filesystem"] == "nsfs"
    result = observe(manifest, locator, context)
    evidence = result["parents"]["evidence"]
    assert evidence["containing_mount"]["mount_id"] == 13
    assert evidence["containing_mount"]["filesystem"] == "nsfs"
    assert evidence["filesystem_qualified"] is False
    assert evidence["peak_and_persistence_qualified"] is False
    assert result["field_ready"] is False
    assert result["allow_run"] is False
    assert calls == ["boot", "mountinfo"]


@pytest.mark.parametrize("root", [
    "mnt:[]", "mnt:[0]", "mnt:[01]", "mnt:[-1]", "mnt:[+1]", "mnt:[a]",
    "mnt:[1", "mnt:1]", "mnt:[1]/child", "unknown:[1]",
    "mnt:[9223372036854775808]", "mnt:[" + "1" * 100 + "]",
])
def test_invalid_namespace_root_notation_is_rejected(root):
    raw = f"13 10 0:4 {root} /run/example.mnt rw - nsfs nsfs rw\n".encode()
    with pytest.raises(ValueError, match="NSFS_ROOT"):
        m.parse_mountinfo(raw)


@pytest.mark.parametrize("raw", [
    b"13 10 8:1 mnt:[4026531840] /run/example.mnt rw - ext4 /dev/root rw\n",
    b"13 10 0:4 mnt:[4026531840] mnt:[4026531840] rw - nsfs nsfs rw\n",
    b"13 10 0:4 mnt:[4026531840] /../run/example.mnt rw - nsfs nsfs rw\n",
    b"13 10 0:4 /../root /run/example.mnt rw - nsfs nsfs rw\n",
])
def test_nsfs_root_exception_does_not_bypass_other_path_checks(raw):
    with pytest.raises(ValueError, match="MOUNTINFO_PATH"):
        m.parse_mountinfo(raw)


def test_static_call_boundary_has_no_alternate_reader_or_privilege_path():
    source = Path(m.__file__).read_text()
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    read_calls = [node for node in calls if isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "kernel"
        and node.func.attr == "read_fact"]
    assert len(read_calls) == 2
    assert [node.args[0].value for node in read_calls] == ["boot", "mountinfo"]
    signature = inspect.signature(m.observe)
    assert list(signature.parameters) == ["manifest_raw", "locator_raw",
        "context_raw", "implementation_commit", "implementation_tree"]
    assert signature.parameters["implementation_commit"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["implementation_tree"].kind is inspect.Parameter.KEYWORD_ONLY
    assert "O_NOATIME" not in source and "subprocess" not in source
    assert not any(isinstance(node, ast.Name) and node.id in {"sudo", "setuid", "setgid"}
        for node in ast.walk(tree))
    assert m.KERNEL_AUTHORITY == {
        "scope": "LH-Q2-KERNEL-FACT-READ-v1",
        "baseline": "887b640b394f9983f37dfe97c58ba35aaa099359",
        "closure": "f7f8b503470725ca1ba18d1cb8d8b39e09a15ea8",
        "implementation": "e15c633adbdfbf1e29cb12b2410975fe4911458d",
    }
