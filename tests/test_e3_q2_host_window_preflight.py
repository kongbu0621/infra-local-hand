"""Real protected local reads with synthetic source pins; no host/guest run.

Private locators, original input verification and kernel text are substituted
explicitly. Filesystem reads, O_NOATIME, metadata, ACL observations and path
checks are real. Ordinary-user proc O_NOATIME capability is not established.
These tests establish neither the private inputs nor execution readiness.
"""
import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import pytest

from e3_host import q2_host_window_preflight as m


BOOT = "00000000-0000-0000-0000-000000000001"
REAL_KERNEL_TEXT, REAL_BOOT = m._kernel_text, m._boot


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


@pytest.fixture
def setup(monkeypatch):
    home = Path.home()
    if sys.platform != "linux" or any(os.stat(path).st_mode & 0o022 for path in (home, *home.parents)):
        pytest.skip("No Linux protected temporary parent")
    with tempfile.TemporaryDirectory(prefix="host-local-only-test-", dir=home) as directory:
        parent = Path(directory)
        roots = [parent / ("history-" + letter) for letter in "abcde"]
        for root in roots:
            root.mkdir(mode=0o700)
        proof = encoded(dict(directory=dict(path=str(roots[0]))))
        old_names = ["intent.json", "probe-capture.json", "guest.stdout", "original-capture-proof.json",
            "report.json", "guest.stderr", "clock-anchor.json"]
        files = {name: proof if name == "original-capture-proof.json" else (name + " retained\n").encode()
            for name in old_names}
        pins = {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}
        for name, raw in files.items():
            (roots[1] / name).write_bytes(raw)
            (roots[1] / name).chmod(0o600)
        for root, count in ((roots[0], 5), (roots[2], 10), (roots[3], 10), (roots[4], 5)):
            for i in range(count):
                (root / ("evidence-" + str(i))).write_bytes(b"retained bytes\n")
                (root / ("evidence-" + str(i))).chmod(0o600)
        rows = []
        for root in roots:
            rows.append(dict(source_path=str(root), type="directory", source_metadata=dict(path=str(root))))
            for child in root.iterdir():
                rows.append(dict(source_path=str(child), type="regular", source_metadata=dict(path=str(child))))
        siblings = [parent / ("unclassified-sibling-" + str(i)) for i in range(7)]
        for sibling in siblings:
            rows.append(dict(source_path=str(sibling), type="regular", source_metadata=dict(path=str(sibling))))
        manifest = encoded(dict(entries=rows, entry_count=len(rows)))
        assert len(rows) == 49
        carrier = ("HOST_RESULT=" + repr(str(roots[2])) + "\nHOST_OLD=" + repr(str(roots[1])) +
            "\nOLD_HOST_FILES=" + repr(pins) + "\n").encode()
        location = dict(parent=str(parent), directory=str(parent / m.c.DIRECTORY_NAME), expected_boot_id=BOOT)
        selected_sources = dict(host_manifest_raw=manifest, original_capture_proof_raw=proof)
        config = dict(old_host_files=[dict(path=str(roots[1] / name), sha256=digest) for name, digest in sorted(pins.items())])
        verified = SimpleNamespace(implementation_commit="a" * 40,
            execution=dict(source=dict(tree="b" * 40)), digest="c" * 64)
        monkeypatch.setattr(m, "LOCATOR_SHA256", hashlib.sha256(manifest).hexdigest())
        monkeypatch.setattr(m, "LOCATOR_BYTES", len(manifest))
        monkeypatch.setattr(m, "CAPTURE_PROOF_SHA256", hashlib.sha256(proof).hexdigest())
        monkeypatch.setattr(m, "CAPTURE_PROOF_BYTES", len(proof))
        monkeypatch.setattr(m.c, "sources", lambda *args: copy.deepcopy(location))
        real_helper = m.helper
        monkeypatch.setattr(m, "helper", lambda name: SimpleNamespace(
            offline_inputs=lambda *args: (verified, copy.deepcopy(location)))
            if name == "q2_reconciliation_entry" else real_helper(name))
        monkeypatch.setattr(m, "_boot", lambda guard: (guard(), BOOT)[1])
        # The cloud process PID namespace differs from its exposed proc mount.
        # This is synthetic kernel data, not evidence about an authorized host.
        monkeypatch.setattr(m, "_kernel_text", lambda path, guard, maximum:
            (guard(), b"1 0 0:1 / / rw - synthetic synthetic rw\n")[1])
        try:
            yield SimpleNamespace(parent=parent, roots=roots, files=files, carrier=carrier,
                location=location, config=config, proof=selected_sources, siblings=siblings)
        finally:
            # Undo mutation-denial spies before TemporaryDirectory cleanup.
            monkeypatch.undo()


def run(setup, **kwargs):
    return m.run_local(setup.config, {}, setup.carrier, b"synthetic-host-attestation",
        host_source_proof=setup.proof, **kwargs)


def test_fixed_locators_are_not_historical_adoption_or_arbitrary_paths(setup):
    result = m.targets(setup.carrier, b"synthetic", setup.proof, config=setup.config)
    assert result["roots"] == sorted(map(str, setup.roots))
    assert result["source_role"] == "KNOWN_OBJECT_LOCATOR_ONLY"
    assert result["current_observation_not_adoption"] is True
    assert result["historical_identity_adopted"] is False
    assert len(result["locator_only_roots"]) == 2
    wrong = dict(setup.proof, paths=["/unapproved"])
    with pytest.raises(ValueError):
        m.targets(setup.carrier, b"synthetic", wrong)
    wrong = copy.deepcopy(setup.config)
    wrong["old_host_files"][0]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="CONFIG_OLD_PINS"):
        m.targets(setup.carrier, b"synthetic", setup.proof, config=wrong)


def test_locator_digest_and_length_are_not_caller_selected(setup):
    for key in setup.proof:
        bad = dict(setup.proof)
        bad[key] += b" "
        with pytest.raises(ValueError, match="PIN"):
            m.targets(setup.carrier, b"synthetic", bad)


def test_real_local_reads_preserve_metadata_and_never_write_or_dispatch(setup, monkeypatch):
    before = {str(path): m.io.metadata(path.stat()) for root in setup.roots for path in (root, *root.iterdir())}
    real_open = os.open
    real_read, real_scandir, real_close = os.read, os.scandir, os.close
    opened = []
    metadata_only = set()
    def read_only_open(path, flags, *args, **kwargs):
        assert flags & os.O_ACCMODE == os.O_RDONLY
        assert not flags & (os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        assert flags & os.O_PATH or flags & os.O_NOATIME or path == "."
        opened.append(path)
        fd = real_open(path, flags, *args, **kwargs)
        if not flags & (os.O_PATH | os.O_NOATIME): metadata_only.add(fd)
        return fd
    def content_read(fd, *args, **kwargs):
        assert fd not in metadata_only
        return real_read(fd, *args, **kwargs)
    def enumerate_directory(fd, *args, **kwargs):
        assert fd not in metadata_only
        return real_scandir(fd, *args, **kwargs)
    def close(fd):
        metadata_only.discard(fd)
        return real_close(fd)
    monkeypatch.setattr(m.os, "open", read_only_open)
    monkeypatch.setattr(m.os, "read", content_read)
    monkeypatch.setattr(m.os, "scandir", enumerate_directory)
    monkeypatch.setattr(m.os, "close", close)
    for name in ("mkdir", "write", "fsync", "rename", "replace", "unlink", "utime", "chmod", "setxattr"):
        monkeypatch.setattr(m.os, name, lambda *args, _name=name, **kwargs: pytest.fail("mutation: " + _name))
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: pytest.fail("subprocess"))
    report = run(setup)
    assert report["status"] == "OBSERVED_PARTIAL", report
    assert report["observations"]["five_trees_complete"] is True
    assert report["observations"]["observed_unique_inodes"] == 42
    assert len(report["observations"]["old_pin_matches"]) == 7
    assert report["observations"]["capture_bill_bytes"] is None
    assert report["observations"]["historical_future_bytes"] is None
    assert report["observations"]["native_audit_peak_bytes"] is None
    assert report["observations"]["filesystem"]["durability_proven"] is False
    assert len(m.encode_report(report)) <= m.OUTPUT_LIMIT - 16384
    assert not any(report[key] for key in ("allow_run", "allow_consume", "host_persistence_attempted",
        "remote_attempted", "window_consumed_by_this_invocation", "joint_admission_proven"))
    assert before == {path: m.io.metadata(os.stat(path)) for path in before}
    assert not any(path.exists() for path in setup.siblings)
    assert not Path(setup.location["directory"]).exists()


def test_wrong_boot_stops_before_parent_open(setup, monkeypatch):
    monkeypatch.setattr(m, "_boot", lambda guard: "00000000-0000-0000-0000-000000000002")
    monkeypatch.setattr(m.io, "HeldPath", lambda *args, **kwargs: pytest.fail("parent read"))
    report = run(setup)
    assert report["reason"] == "HOST_LOCAL_BOOT_CHANGED"
    assert report["consumption_path_state"] == "NOT_OBSERVED"


@pytest.mark.parametrize("kind", ["directory", "file", "symlink"])
def test_any_marker_stops_before_enumeration_or_mount_query(setup, monkeypatch, kind):
    marker = Path(setup.location["directory"])
    if kind == "directory": marker.mkdir()
    elif kind == "file": marker.write_bytes(b"partial")
    else: marker.symlink_to(setup.roots[0])
    monkeypatch.setattr(m.os, "scandir", lambda *args: pytest.fail("tree enumeration"))
    monkeypatch.setattr(m, "_mount_observation", lambda *args: pytest.fail("mount query"))
    report = run(setup)
    assert report["reason"] == "HOST_LOCAL_ALREADY_CONSUMED_OR_UNCERTAIN"
    assert report["consumption_path_state"] == "EXISTING_PATH_BLOCKED"
    assert report["window_consumed_by_this_invocation"] is False


def test_noatime_denied_never_reopens_with_weaker_flags(setup, monkeypatch):
    calls = []
    real_open = os.open
    def refused(path, flags, *args, **kwargs):
        if path == setup.parent.name:
            calls.append(flags)
            raise PermissionError(errno.EPERM, "noatime not permitted")
        return real_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(m.os, "open", refused)
    report = run(setup)
    assert report["reason"] == "PermissionError"
    assert len(calls) == 1 and calls[0] & os.O_NOATIME


def test_root_owned_kernel_noatime_denial_is_explicit_without_fallback(setup, monkeypatch):
    monkeypatch.setattr(m, "_kernel_text", REAL_KERNEL_TEXT)
    monkeypatch.setattr(m, "_boot", REAL_BOOT)
    real_open, attempts = os.open, []
    def refused(path, flags, *args, **kwargs):
        if path == "boot_id":
            attempts.append(flags)
            raise PermissionError(errno.EPERM, "synthetic ordinary-user noatime denial")
        return real_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(m.os, "open", refused)
    report = run(setup)
    assert report["reason"] == "HOST_LOCAL_KERNEL_NOATIME_PERMISSION"
    assert report["stage"] == "host_boot"
    assert report["consumption_path_state"] == "NOT_OBSERVED"
    assert len(attempts) == 1 and attempts[0] & os.O_NOATIME


def test_kernel_content_limit_is_not_a_silent_prefix(setup):
    sample = setup.roots[0] / "evidence-0"
    before = m.io.metadata(sample.stat())
    with pytest.raises(ValueError, match="KERNEL_READ_LIMIT"):
        REAL_KERNEL_TEXT(str(sample), lambda: None, 1)
    assert m.io.metadata(sample.stat()) == before


@pytest.mark.parametrize("error", [None, errno.EOPNOTSUPP])
def test_acl_present_or_unknown_stops_without_permission_change(setup, monkeypatch, error):
    def acl(*args):
        if error is not None: raise OSError(error, "unsupported")
        return b"untrusted ACL"
    monkeypatch.setattr(m.os, "getxattr", acl)
    report = run(setup)
    assert report["reason"] == ("HOST_LOCAL_ACL_PRESENT" if error is None else "HOST_LOCAL_ACL_UNSUPPORTED")


def test_metadata_drift_during_content_read_is_retained_as_failure(setup, monkeypatch):
    digest = m.io._digest
    changed = []
    def raced(fd, guard, limit):
        value = digest(fd, guard, limit)
        if not changed:
            target = setup.roots[0] / "evidence-0"
            target.chmod(0o400)
            changed.append(target)
        return value
    monkeypatch.setattr(m.io, "_digest", raced)
    report = run(setup)
    assert report["status"] == "LOCAL_PREFLIGHT_BLOCKED"
    assert "CHANGED" in report["reason"]


def test_original_pin_change_is_not_adopted(setup):
    target = setup.roots[1] / "intent.json"
    target.write_bytes(b"unexpected replacement")
    report = run(setup)
    assert report["reason"] == "HOST_LOCAL_OLD_PIN_CHANGED"
    assert report["allow_consume"] is False


@pytest.mark.parametrize("bound", ["MAX_ENTRIES", "MAX_READ_BYTES"])
def test_tree_work_has_fixed_bounds(setup, monkeypatch, bound):
    monkeypatch.setattr(m, bound, 1)
    report = run(setup)
    assert report["status"] == "LOCAL_PREFLIGHT_BLOCKED"
    assert report["reason"] in ("HOST_LOCAL_ENTRY_LIMIT", "HOST_LOCAL_READ_LIMIT")


def test_report_budget_returns_bounded_failure_with_no_admission(setup, monkeypatch):
    monkeypatch.setattr(m, "REPORT_LIMIT", 8192)
    report = run(setup)
    assert report["status"] == "LOCAL_PREFLIGHT_BLOCKED"
    assert report["reason"] == "HOST_LOCAL_OUTPUT_LIMIT"
    assert report["observations"] == {"omitted_due_to_output_limit": True}
    assert len(m.encode_report(report)) <= 8192
    assert report["allow_consume"] is report["allow_run"] is False


def test_receiver_origin_is_retained_without_resampling(setup, monkeypatch):
    now = [100 * m.c.NS]
    monkeypatch.setattr(m.delivery.time, "monotonic_ns", lambda: now[0])
    monkeypatch.setattr(m.delivery.time, "clock_gettime_ns", lambda _: now[0])
    origin = dict(issued_ns=90 * m.c.NS, deadline_ns=390 * m.c.NS,
        boottime_issued_ns=90 * m.c.NS, boottime_deadline_ns=390 * m.c.NS)
    report = run(setup, reception_window=origin)
    assert report["status"] == "OBSERVED_PARTIAL", report
    assert report["window"] == origin
    assert report["preparation_deadline_ns"] == 230 * m.c.NS


def test_expired_receiver_and_changed_origin_refuse_before_field_reads(setup, monkeypatch):
    now = 250 * m.c.NS
    monkeypatch.setattr(m.delivery.time, "monotonic_ns", lambda: now)
    monkeypatch.setattr(m.delivery.time, "clock_gettime_ns", lambda _: now)
    monkeypatch.setattr(m, "_boot", lambda guard: pytest.fail("expired field read"))
    origin = dict(issued_ns=100 * m.c.NS, deadline_ns=400 * m.c.NS,
        boottime_issued_ns=100 * m.c.NS, boottime_deadline_ns=400 * m.c.NS)
    report = run(setup, reception_window=origin)
    assert report["reason"] == "HOST_LOCAL_PREPARATION_EXPIRED"
    assert report["field_reads_performed"] is False
    origin["deadline_ns"] += 1
    assert run(setup, reception_window=origin)["reason"] == "HOST_WINDOW_DEADLINE"


def test_boottime_alone_expires_preparation_before_reads(setup, monkeypatch):
    monkeypatch.setattr(m.delivery.time, "monotonic_ns", lambda: 110 * m.c.NS)
    monkeypatch.setattr(m.delivery.time, "clock_gettime_ns", lambda _: 241 * m.c.NS)
    monkeypatch.setattr(m, "_boot", lambda guard: pytest.fail("expired field read"))
    origin = dict(issued_ns=100 * m.c.NS, deadline_ns=400 * m.c.NS,
        boottime_issued_ns=100 * m.c.NS, boottime_deadline_ns=400 * m.c.NS)
    report = run(setup, reception_window=origin)
    assert report["status"] == "LOCAL_PREFLIGHT_BLOCKED"
    assert report["field_reads_performed"] is False


def test_source_failure_precedes_any_clock_or_live_fact(setup, monkeypatch):
    monkeypatch.setattr(m, "_window", lambda *args: pytest.fail("window began"))
    setup.proof["host_manifest_raw"] += b" "
    report = run(setup)
    assert report["reason"] == "HOST_LOCAL_LOCATOR_PIN"
    assert report["local_preflight_started"] is False
    assert report["field_reads_performed"] is False


def test_module_has_no_write_dispatch_or_marker_consumption_calls():
    import ast
    tree = ast.parse(Path(m.__file__).read_bytes())
    forbidden = {"consume", "mkdir", "write", "fsync", "Popen", "run", "call", "system", "execv",
        "unlink", "rename", "replace", "chmod", "utime", "setxattr", "require_field_readiness"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden for node in ast.walk(tree))
