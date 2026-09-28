"""Synthetic pins/kernel/identity isolate real noatime, ACL and fd behavior.

The ordinary-identity test below separately uses real credentials and labels
unavailable credentials SKIP. No synthetic result is original-host evidence.
"""
import base64
import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

import pytest

if sys.platform != "linux":
    pytest.skip("Approved local-source observer is Linux only", allow_module_level=True)

from e3_host import q2_local_source_observe as m


BOOT = "00000000-0000-0000-0000-000000000001"
FIXTURE_PARENT_ENV = "LOCAL_HAND_Q2_TEST_PARENT"


def fixture_parent():
    """Test setup only; production never accepts this environment override.

    CI supplies a fresh ordinary-owned directory under a protected root ancestor.
    An explicit fixture must qualify with real credentials/ACLs or fail; there
    is no fallback to home and no modification of an existing ancestor's ACL.
    """
    supplied = os.environ.get(FIXTURE_PARENT_ENV)
    if supplied is not None:
        original = m.identity()  # A configured CI fixture requires real nonroot.
        def guard():
            assert m.identity() == original
        parent = Path(m.io.absolute(supplied))
    else:
        parent, guard = Path.home(), lambda: None
    with m.io.HeldPath(str(parent), guard, directory=True) as held:
        m._chain(held, guard)
    return parent


def window():
    boot, mono = time.clock_gettime_ns(time.CLOCK_BOOTTIME), time.monotonic_ns()
    return dict(issued_ns=mono, deadline_ns=mono + 300 * m.NS,
        boottime_issued_ns=boot, boottime_deadline_ns=boot + 300 * m.NS)


def binding():
    return dict(authority=dict(rule=m.c.RULE, baseline=m.c.BASELINE, closure=m.c.CLOSURE,
        owner_decision=m.c.OWNER_DECISION, scope=m.c.SCOPE), implementation_commit="a" * 40,
        implementation_tree="b" * 40, tools_sha256="c" * 64, package_sha256="d" * 64,
        package_bytes=500, transport=dict(receiver_source_sha256="e" * 64,
            receiver_command_bytes=100, frame_bytes=1000, payload_input_bytes=1100,
            package_bytes=500, package_sha256="d" * 64))


@pytest.fixture
def setup(monkeypatch):
    home = fixture_parent()
    with tempfile.TemporaryDirectory(prefix="local-source-observe-", dir=home) as directory:
        root = Path(directory)
        host, control = root / "host", root / "control"
        host.mkdir(mode=0o700); control.mkdir(mode=0o700)
        targets, files = [], {}
        for index in range(11):
            source, number, parent = ("M", index + 1, host) if index < 7 else ("T", index - 6, control)
            logical = "%s%02d" % (source, number)
            path, raw = parent / logical, (logical + " approved synthetic data\n").encode()
            path.write_bytes(raw); path.chmod(0o600)
            files[logical] = path
            targets.append(dict(id=logical, path=str(path), parent=str(parent), source=source,
                source_role="SYNTHETIC_TEST_ONLY", source_index=index, size_cap=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(), return_raw=source == "T"))
        derived = dict(location=dict(host_parent=str(host), control_parent=str(control),
            marker_name=m.c.DIRECTORY_NAME, marker_path=str(host / m.c.DIRECTORY_NAME),
            expected_boot_id=BOOT, startup_closure=m.c.STARTUP_CLOSURE), targets=targets,
            sources={key: dict(bytes=1, sha256="f" * 64) for key in "PMT"}, target_manifest_sha256="f" * 64)
        monkeypatch.setattr(m.c, "targets", lambda *args: copy.deepcopy(derived))
        # Synthetic identity intentionally does not establish ordinary-user PASS.
        synthetic_uid = os.geteuid() or 1000
        synthetic = dict(uid=[synthetic_uid] * 3, gid=[os.getegid()] * 3,
            supplementary_groups=sorted(os.getgroups()))
        monkeypatch.setattr(m, "identity", lambda: copy.deepcopy(synthetic))
        device = host.stat().st_dev
        mount = ("1 0 %s:%s / / rw - synthetic synthetic rw\n" %
            (os.major(device), os.minor(device))).encode()
        kernel_calls = []
        def kernel(kind, guard, report):
            guard(); kernel_calls.append(kind)
            raw = (BOOT + "\n").encode() if kind == "boot" else mount
            report.update(target=kind, status="SYNTHETIC_TEST_ONLY", bytes=len(raw), bytes_observed=len(raw))
            return raw
        monkeypatch.setattr(m.kernel, "read_fact", kernel)
        yield SimpleNamespace(root=root, host=host, control=control, files=files, derived=derived,
            targets=targets, identity=synthetic, kernel_calls=kernel_calls, kernel=kernel, mount=mount)
        monkeypatch.undo()


def run(setup, **kwargs):
    return m.run_local(b"P", b"M", b"T", reception_window=kwargs.pop("reception_window", window()),
        binding=kwargs.pop("binding", binding()), **kwargs)


def test_exact_eleven_single_reads_preserve_metadata_without_writes_scans_or_processes(setup, monkeypatch):
    before = {path: m.io.metadata(path.stat()) for path in [setup.host, setup.control, *setup.files.values()]}
    real_open, real_read, real_close = os.open, os.read, os.close
    files_by_fd, reads, opens = {}, {}, []
    def tracked_open(name, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        assert flags & os.O_PATH or flags & os.O_NOATIME or name == "."
        fd = real_open(name, flags, *args, **kwargs)
        files_by_fd[fd] = str(name)
        opens.append((str(name), flags))
        return fd
    def tracked_read(fd, count):
        name = files_by_fd[fd]
        assert name in setup.files, "Only fixed target content may be read"
        raw = real_read(fd, count)
        reads.setdefault(name, []).append((count, len(raw)))
        return raw
    def close(fd):
        files_by_fd.pop(fd, None)
        return real_close(fd)
    monkeypatch.setattr(os, "open", tracked_open)
    monkeypatch.setattr(os, "read", tracked_read)
    monkeypatch.setattr(os, "close", close)
    monkeypatch.setattr(os, "scandir", lambda *a, **kw: pytest.fail("No directory scans"))
    monkeypatch.setattr(os, "listdir", lambda *a, **kw: pytest.fail("No directory enumeration"))
    monkeypatch.setattr(os, "write", lambda *a, **kw: pytest.fail("No writes"))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: pytest.fail("No subprocess"))
    result = run(setup)
    assert result["status"] == "OBSERVED_PARTIAL", result.get("error")
    assert result["completion"] == dict(attempted=11, observed=11, matched=11, raw_returned=4, expected_objects=11)
    assert list(reads) == list(setup.files)
    assert all(len(calls) == 2 and calls[-1] == (1, 0) for calls in reads.values())
    assert result["byte_counts"]["ordinary_actual_read"] == sum(item["size_cap"] for item in setup.targets)
    assert result["byte_counts"]["kernel_actual_read"] == 2 * 37 + len(setup.mount)
    assert result["byte_counts"]["output_json_bytes"] == len(m.encoded(result))
    assert setup.kernel_calls == ["boot", "mountinfo", "boot"]
    assert len(result["parent_filesystems"]) == 2
    assert all(value["state"] == "ABSENT_AT_OBSERVATION" for value in result["marker_observations"])
    assert all(result[name] is False for name in m.c.DENIED_FLAGS)
    assert result["historical_costs_adopted"] is result["h07_proven"] is False
    assert result["current_observed_totals"]["atomic_snapshot"] is False
    for item in result["objects"]:
        if item["source"] == "M":
            assert "raw_base64" not in item
        else:
            assert hashlib.sha256(base64.b64decode(item["raw_base64"])).hexdigest() == item["observed_sha256"]
        assert item["source_sha256"] == item["observed_sha256"]
        assert "sha256" not in item
    assert before == {path: m.io.metadata(path.stat()) for path in before}
    assert not files_by_fd


@pytest.mark.parametrize("source", ("M01", "T01"))
@pytest.mark.parametrize("fault", ("missing", "size", "digest"))
def test_stable_differences_continue_without_adoption_or_unmatched_raw(setup, source, fault):
    path = setup.files[source]
    if fault == "missing": path.unlink()
    elif fault == "size": path.write_bytes(b"changed length")
    else: path.write_bytes(b"x" * path.stat().st_size)
    result = run(setup)
    row = next(item for item in result["objects"] if item["id"] == source)
    assert result["status"] == "OBSERVED_PARTIAL", result.get("error")
    assert row["status"] == {"missing": "CURRENT_MISSING", "size": "CURRENT_LENGTH_CHANGED",
        "digest": "CURRENT_DIGEST_CHANGED"}[fault]
    assert "raw_base64" not in row
    assert "sha256" not in row
    assert row["source_sha256"] == next(item["sha256"] for item in setup.targets if item["id"] == source)
    if fault == "digest":
        assert row["observed_sha256"] == hashlib.sha256(b"x" * path.stat().st_size).hexdigest()
        assert row["observed_sha256"] != row["source_sha256"] and not row["sha256_matches_source"]
    else:
        assert "observed_sha256" not in row and "sha256_matches_source" not in row
    assert row["actual_read_bytes"] == (path.stat().st_size if fault == "digest" else 0)
    assert result["completion"]["observed"] == 11 and result["completion"]["matched"] == 10
    assert result["objects"][-1]["status"] == "MATCHED"


@pytest.mark.parametrize("fault", ("symlink", "hardlink", "mode", "setgid", "directory", "acl", "noatime"))
def test_protection_failures_stop_remaining_fixed_targets(setup, monkeypatch, fault):
    path = setup.files["M01"]
    if fault == "symlink":
        path.unlink(); path.symlink_to(setup.files["M02"])
    elif fault == "hardlink": os.link(path, setup.host / "alias")
    elif fault == "mode": path.chmod(0o620)
    elif fault == "setgid": path.chmod(0o2600)
    elif fault == "directory": path.unlink(); path.mkdir()
    elif fault == "acl":
        real = os.getxattr
        monkeypatch.setattr(os, "getxattr", lambda fd, name: b"acl" if os.fstat(fd).st_ino == path.stat().st_ino
            else real(fd, name))
    elif fault == "noatime":
        real = os.open
        def denied(name, flags, **kwargs):
            if name == "M01": raise PermissionError(errno.EPERM, "synthetic noatime failure")
            return real(name, flags, **kwargs)
        monkeypatch.setattr(os, "open", denied)
    result = run(setup)
    assert result["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED"
    assert result["objects"][0]["status"] == "BLOCKED"
    assert all(row["status"] == "NOT_ATTEMPTED" for row in result["objects"][1:])
    assert all("observed_sha256" not in row and "sha256" not in row and "sha256_matches_source" not in row
        for row in result["objects"])
    assert result["byte_counts"]["ordinary_actual_read"] == 0
    assert setup.kernel_calls == ["boot", "mountinfo"]


@pytest.mark.parametrize("fault", ("short", "long", "metadata", "name", "identity", "groups", "deadline"))
def test_midread_failures_account_actual_bytes_and_never_return_unverified_raw(setup, monkeypatch, fault):
    real_read = os.read
    wanted = setup.files["T01"].stat().st_ino
    mutated, observed = False, 0
    def read(fd, count):
        nonlocal mutated, observed
        relevant = os.fstat(fd).st_ino == wanted
        if relevant and fault == "short": return b""
        block = real_read(fd, count)
        if relevant:
            if fault == "long" and not block: block = b"x"
            observed += len(block)
            if not mutated and block:
                mutated = True
                if fault == "metadata": os.utime(setup.files["T01"], ns=(1, 2))
                if fault == "name":
                    setup.files["T01"].rename(setup.control / "original")
                    setup.files["T01"].write_bytes(block)
                if fault == "identity": setup.identity["uid"] = [setup.identity["uid"][0] + 1] * 3
                if fault == "groups": setup.identity["supplementary_groups"].append(2**31)
                if fault == "deadline":
                    monkeypatch.setattr(m.time, "monotonic_ns", lambda: origin["issued_ns"] + 140 * m.NS)
        return block
    origin = window()
    monkeypatch.setattr(os, "read", read)
    result = run(setup, reception_window=origin)
    target = result["objects"][7]
    assert result["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED", result
    assert target["status"] == "BLOCKED" and "raw_base64" not in target
    assert "observed_sha256" not in target and "sha256_matches_source" not in target
    assert target["actual_read_bytes"] == observed
    assert result["byte_counts"]["ordinary_actual_read"] == sum(row["size_cap"] for row in setup.targets[:7]) + observed
    assert all(row["status"] == "NOT_ATTEMPTED" for row in result["objects"][8:])


@pytest.mark.parametrize("fault", ("existing", "symlink", "uncertain"))
def test_marker_always_blocks_before_mountinfo_or_file_reads(setup, monkeypatch, fault):
    marker = setup.host / m.c.DIRECTORY_NAME
    if fault == "existing": marker.mkdir()
    elif fault == "symlink": marker.symlink_to("missing-target")
    else:
        real = os.stat
        def uncertain(path, *args, **kwargs):
            if path == m.c.DIRECTORY_NAME: raise PermissionError(errno.EACCES, "uncertain")
            return real(path, *args, **kwargs)
        monkeypatch.setattr(os, "stat", uncertain)
    result = run(setup)
    assert result["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED"
    assert setup.kernel_calls == ["boot"]
    assert result["completion"]["attempted"] == 0
    assert result["window_consumed_by_this_invocation"] is False


def test_ancestor_acl_failure_is_fatal_before_content_or_marker(setup, monkeypatch):
    real = os.getxattr
    ancestor = setup.root.stat().st_ino
    def acl(fd, name):
        if os.fstat(fd).st_ino == ancestor: raise OSError(errno.ENOTSUP, "unknown ancestor ACL")
        return real(fd, name)
    monkeypatch.setattr(os, "getxattr", acl)
    result = run(setup)
    assert result["error"]["reason"] == "LOCAL_SOURCE_ACL_UNSUPPORTED"
    assert result["marker_observations"] == [] and result["completion"]["attempted"] == 0


@pytest.mark.parametrize("stage", ("first", "last"))
def test_boot_change_stops_at_actual_scope_without_rerun(setup, monkeypatch, stage):
    calls = 0
    def kernel(kind, guard, report):
        nonlocal calls
        raw = setup.kernel(kind, guard, report)
        if kind == "boot":
            calls += 1
            if calls == (1 if stage == "first" else 2): raw = raw.replace(b"001", b"002")
        return raw
    monkeypatch.setattr(m.kernel, "read_fact", kernel)
    result = run(setup)
    assert result["error"]["reason"] == "LOCAL_SOURCE_BOOT_CHANGED"
    assert result["completion"]["attempted"] == (0 if stage == "first" else 11)
    assert calls == (1 if stage == "first" else 2)


@pytest.mark.parametrize("error", (errno.ENOTTY, errno.EOPNOTSUPP, errno.EPERM))
def test_filesystem_flags_distinguish_unsupported_from_permission_failure(setup, monkeypatch, error):
    def unavailable(*args): raise OSError(error, "synthetic ioctl error")
    monkeypatch.setattr(m.fcntl, "ioctl", unavailable)
    result = run(setup)
    if error == errno.EPERM:
        assert result["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED" and result["completion"]["attempted"] == 0
    else:
        assert result["status"] == "OBSERVED_PARTIAL"
        assert all(row["parent_flags"] == dict(status="UNSUPPORTED", errno=error) for row in result["parent_filesystems"])
        assert result["allocation_peak_proven"] is result["durability_proven"] is False


@pytest.mark.parametrize("error", (errno.ENOSYS, errno.ENOTTY, errno.EOPNOTSUPP, errno.EACCES, errno.EIO))
def test_statvfs_unsupported_retains_unknown_geometry_but_io_errors_stop(setup, monkeypatch, error):
    def unavailable(fd): raise OSError(error, "synthetic statvfs error")
    monkeypatch.setattr(os, "fstatvfs", unavailable)
    result = run(setup)
    if error in (errno.EACCES, errno.EIO):
        assert result["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED" and result["completion"]["attempted"] == 0
    else:
        assert result["status"] == "OBSERVED_PARTIAL"
        assert all(row["statvfs"] == dict(status="UNSUPPORTED", errno=error) for row in result["parent_filesystems"])
        assert result["allocation_peak_proven"] is result["durability_proven"] is False


@pytest.mark.parametrize("fault", ("parent_mode", "parent_name", "marker_during_read"))
def test_parent_or_marker_changes_mid_observation_stop_without_successor_reads(setup, monkeypatch, fault):
    read = os.read
    mutated = False
    def change(fd, count):
        nonlocal mutated
        raw = read(fd, count)
        if raw and not mutated:
            mutated = True
            if fault == "parent_mode": setup.host.chmod(0o750)
            if fault == "parent_name": setup.host.rename(setup.root / "previous-host")
            if fault == "marker_during_read": (setup.host / m.c.DIRECTORY_NAME).mkdir()
        return raw
    monkeypatch.setattr(os, "read", change)
    result = run(setup)
    assert result["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED"
    assert result["objects"][0]["status"] == "BLOCKED"
    assert all(row["status"] == "NOT_ATTEMPTED" for row in result["objects"][1:])
    assert result["byte_counts"]["ordinary_actual_read"] == setup.targets[0]["size_cap"]
    assert result["window_consumed_by_this_invocation"] is False


def test_same_parent_inode_for_two_derived_parents_rejected_before_marker(setup):
    # An alternate mount alias is modeled by equal held identities, without
    # granting arbitrary paths to the real source parser.
    setup.derived["location"]["control_parent"] = str(setup.host)
    result = run(setup)
    assert result["error"]["reason"] == "LOCAL_SOURCE_PARENT_ALIAS"
    assert result["marker_observations"] == [] and result["completion"]["attempted"] == 0


def test_repeated_object_identity_is_rejected_even_if_link_count_is_one(setup):
    # This models a bind alias; real hardlinks independently fail nlink checks.
    setup.targets[1]["path"] = setup.targets[0]["path"]
    result = run(setup)
    assert result["objects"][0]["status"] == "MATCHED"
    assert result["objects"][1]["status"] == "BLOCKED"
    assert result["error"]["reason"] == "LOCAL_SOURCE_OBJECT_ALIAS"
    assert all(row["status"] == "NOT_ATTEMPTED" for row in result["objects"][2:])


def test_file_replacement_between_name_stat_and_open_never_reads_replacement(setup, monkeypatch):
    real_open, read = os.open, os.read
    def replace(name, flags, **kwargs):
        if name == "M01":
            setup.files["M01"].rename(setup.host / "previous")
            setup.files["M01"].write_bytes(b"new file")
        return real_open(name, flags, **kwargs)
    monkeypatch.setattr(os, "open", replace)
    monkeypatch.setattr(os, "read", lambda *args: pytest.fail("No read of replacement"))
    result = run(setup)
    assert result["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED"
    assert result["byte_counts"]["ordinary_actual_read"] == 0


def test_offline_rejection_precedes_identity_and_every_field_read(setup, monkeypatch):
    def reject(*args): raise ValueError("LOCAL_SOURCE_P_PIN")
    monkeypatch.setattr(m.c, "targets", reject)
    monkeypatch.setattr(m, "identity", lambda: pytest.fail("No identity observation before offline validation"))
    monkeypatch.setattr(os, "open", lambda *a, **kw: pytest.fail("No field open"))
    result = run(setup)
    assert result["error"]["reason"] == "LOCAL_SOURCE_P_PIN" and result["kernel_reads"] == []


@pytest.mark.parametrize("fault", ("missing", "fresh_deadline", "monoexpired", "bootexpired", "rollback", "diverged"))
def test_receiver_original_window_cannot_be_renewed(setup, fault):
    fields = window()
    if fault == "missing": fields = None
    if fault == "fresh_deadline": fields["deadline_ns"] += 1
    if fault == "monoexpired":
        fields["issued_ns"] -= 141 * m.NS; fields["deadline_ns"] -= 141 * m.NS
    if fault == "bootexpired":
        fields["boottime_issued_ns"] -= 141 * m.NS; fields["boottime_deadline_ns"] -= 141 * m.NS
    if fault == "rollback":
        fields["issued_ns"] += 10 * m.NS; fields["deadline_ns"] += 10 * m.NS
    if fault == "diverged":
        fields["boottime_issued_ns"] -= 3 * m.NS; fields["boottime_deadline_ns"] -= 3 * m.NS
    result = run(setup, reception_window=fields)
    assert result["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED" and setup.kernel_calls == []


def test_deadline_crossed_by_final_encoding_is_not_reported_as_success(setup, monkeypatch):
    origin = window()
    original = m.encoded
    def encode(value):
        raw = original(value)
        if value.get("status") == "OBSERVED_PARTIAL":
            monkeypatch.setattr(m.time, "clock_gettime_ns", lambda _: origin["boottime_issued_ns"] + 140 * m.NS)
        return raw
    monkeypatch.setattr(m, "encoded", encode)
    result = run(setup, reception_window=origin)
    assert result["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED"
    assert result["error"]["reason"] in ("LOCAL_SOURCE_ORIGINAL_WINDOW_EXPIRED", "LOCAL_SOURCE_CLOCK_DIVERGED")
    assert result["completion"]["observed"] == 11


def test_output_limit_returns_bounded_incomplete_receipt(setup, monkeypatch):
    monkeypatch.setattr(m.c, "REPORT_LIMIT", 8500)
    result = run(setup)
    assert result["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED"
    assert len(m.encoded(result)) <= 8500
    assert result["completion"]["raw_returned"] == 0
    assert result["completion"]["matched"] < 11


def test_identity_requires_real_effective_saved_agreement_and_nonroot(monkeypatch):
    for uid, gid in (([0, 0, 0], [0, 0, 0]), ([1000, 0, 1000], [1000] * 3),
                     ([1000, 1000, 0], [1000] * 3), ([1000] * 3, [1000, 1000, 0])):
        monkeypatch.setattr(m.os, "getresuid", lambda: tuple(uid))
        monkeypatch.setattr(m.os, "getresgid", lambda: tuple(gid))
        with pytest.raises(ValueError, match="ORDINARY_IDENTITY_REQUIRED"):
            m.identity()


def test_real_ordinary_identity_noatime_acl_and_metadata(capsys):
    # Root may drop credentials only in this isolated fixture process. The
    # production observer never changes credentials or asks for elevation.
    source = str(Path(m.__file__).resolve())
    if FIXTURE_PARENT_ENV in os.environ and os.geteuid() == 0:
        pytest.fail("Configured ordinary fixture cannot be tested as root")
    if os.geteuid() != 0:
        original = m.identity()
        home = fixture_parent()
        def guard():
            assert m.identity() == original
        with tempfile.TemporaryDirectory(prefix="q2-source-ordinary-", dir=home) as directory:
            parent = Path(directory)
            path = parent / "fixed-evidence"
            path.write_bytes(b"ordinary evidence\n"); path.chmod(0o600)
            before, parent_before = m.io.metadata(path.stat()), m.io.metadata(parent.stat())
            with m.io.HeldPath(str(parent), guard, directory=True) as held:
                m._chain(held, guard)
                with m.io.HeldPath(str(path), guard) as file:
                    m._acl(file.fd, guard)
                    raw, eof = os.read(file.fd, 64), os.read(file.fd, 1)
                    file.verify(); guard()
                m._chain(held, guard)
            assert raw == b"ordinary evidence\n" and eof == b""
            assert before == m.io.metadata(path.stat()) and parent_before == m.io.metadata(parent.stat())
            guard()
        with capsys.disabled():
            print("LOCAL_SOURCE_ORDINARY identity=ordinary noatime=PASS ancestor_acl=PASS metadata=STABLE")
        return
    code = r'''
import importlib.util, json, os, pathlib, sys, tempfile
try:
    if os.geteuid() == 0:
        os.setgroups([]); os.setgid(65534); os.setuid(65534)
except OSError as error:
    print(json.dumps(dict(status="IDENTITY_UNAVAILABLE", errno=error.errno))); sys.exit(0)
spec=importlib.util.spec_from_file_location("observe",sys.argv[1]); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
original=m.identity()
home=pathlib.Path.home()
if any(os.stat(p).st_mode & 0o022 for p in (home,*home.parents)) or not os.access(home,os.W_OK):
    print(json.dumps(dict(status="PROTECTED_HOME_UNAVAILABLE"))); sys.exit(0)
def guard():
    if m.identity()!=original: raise ValueError("IDENTITY_CHANGED")
with tempfile.TemporaryDirectory(prefix="q2-source-ordinary-",dir=home) as directory:
    parent=pathlib.Path(directory); path=parent/"fixed-evidence"; path.write_bytes(b"ordinary evidence\n"); path.chmod(0o600)
    before=m.io.metadata(path.stat()); rootbefore=m.io.metadata(parent.stat())
    try:
        with m.io.HeldPath(str(parent),guard,directory=True) as held:
            m._chain(held,guard)
            with m.io.HeldPath(str(path),guard) as file:
                m._acl(file.fd,guard); raw=os.read(file.fd,64); eof=os.read(file.fd,1); file.verify(); guard()
            m._chain(held,guard)
    except (ValueError,OSError) as error:
        print(json.dumps(dict(status="BLOCKED",reason=type(error).__name__,errno=getattr(error,"errno",None)))); sys.exit(0)
    assert raw==b"ordinary evidence\n" and eof==b"" and before==m.io.metadata(path.stat()) and rootbefore==m.io.metadata(parent.stat())
    assert m.identity()==original and original["uid"][1]!=0
print(json.dumps(dict(status="PASS",ordinary_identity=True,noatime=True,metadata_stable=True,ancestor_acl=True)))
'''
    result = subprocess.run([sys.executable, "-I", "-B", "-S", "-c", code, source],
        text=True, capture_output=True, timeout=15, check=True)
    outcome = json.loads(result.stdout)
    if outcome["status"] != "PASS":
        pytest.skip("Real ordinary local source outcome: " + json.dumps(outcome, sort_keys=True))
    assert outcome == dict(status="PASS", ordinary_identity=True, noatime=True, metadata_stable=True, ancestor_acl=True)
    with capsys.disabled():
        print("LOCAL_SOURCE_ORDINARY identity=ordinary noatime=PASS ancestor_acl=PASS metadata=STABLE")


def test_configured_fixture_requires_actual_ordinary_identity_without_skip(monkeypatch):
    monkeypatch.setenv(FIXTURE_PARENT_ENV, str(Path.home()))
    def identity_unavailable():
        raise ValueError("LOCAL_SOURCE_ORDINARY_IDENTITY_REQUIRED")
    monkeypatch.setattr(m, "identity", identity_unavailable)
    with pytest.raises(ValueError, match="ORDINARY_IDENTITY_REQUIRED"):
        fixture_parent()


def test_configured_fixture_acl_failure_has_no_fallback_or_skip(monkeypatch):
    # Pure negative setup control: this synthetic identity does not claim the
    # real ordinary test passed, and no file contents or host facts are read.
    monkeypatch.setenv(FIXTURE_PARENT_ENV, str(Path.home()))
    monkeypatch.setattr(m, "identity", lambda: dict(uid=[1000] * 3, gid=[1000] * 3, supplementary_groups=[]))
    def acl_present(held, guard):
        raise ValueError("LOCAL_SOURCE_ACL_PRESENT")
    monkeypatch.setattr(m, "_chain", acl_present)
    monkeypatch.setattr(Path, "home", lambda: pytest.fail("An explicit test parent cannot fall back to home"))
    with pytest.raises(ValueError, match="LOCAL_SOURCE_ACL_PRESENT"):
        fixture_parent()
