"""Bounded RAM transport and adversarial verification before tool compilation."""
import sys
import pytest

if sys.platform != "linux":
    pytest.skip("Linux RAM receiver requires termios, fcntl and CLOCK_BOOTTIME", allow_module_level=True)

import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import termios
import time
import zipfile

SOURCE = Path(__file__).parent / "e3_host/q2_local_source_delivery.py"


def module():
    spec = importlib.util.spec_from_file_location("_local_source_delivery_test", SOURCE)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def archive(value, files):
    files = dict(files)
    files["package-index.json"] = value.encoded(dict(schema="q2-local-source-package-file-index/v1",
        files={name: dict(bytes=len(raw), sha256=value.sha(raw)) for name, raw in files.items()}))
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, raw in sorted(files.items()):
            zipped.writestr(name, raw)
    return target.getvalue()


@pytest.fixture
def synthetic(monkeypatch):
    """Small genuine Git object graph; synthetic pins never serve field inputs."""
    value = module()
    objects = {}
    def obj(kind, raw):
        oid = hashlib.sha1(kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if kind != "blob":
            objects[oid] = dict(kind=kind, data=base64.b64encode(raw).decode())
        return oid
    def tree(files):
        nested = {}
        for name, raw in files.items():
            parent = nested
            pieces = name.split("/")
            for piece in pieces[:-1]:
                parent = parent.setdefault(piece, {})
            parent[pieces[-1]] = raw
        def visit(parent):
            rows = []
            for name, child in sorted(parent.items()):
                kind = "tree" if isinstance(child, dict) else "blob"
                oid = visit(child) if kind == "tree" else obj(kind, child)
                rows.append((b"40000" if kind == "tree" else b"100644") + b" " + name.encode() + b"\0" + bytes.fromhex(oid))
            return obj("tree", b"".join(rows))
        return visit(nested)
    def commit(root, parent, message):
        raw = b"tree " + root.encode() + b"\n"
        if parent:
            raw += b"parent " + parent.encode() + b"\n"
        return obj("commit", raw + b"author Test <test@example.invalid> 1 +0000\ncommitter Test <test@example.invalid> 1 +0000\n\n" + message.encode() + b"\n")
    shared = {
        "q2_retry_bundle.py": (SOURCE.parent / "q2_retry_bundle.py").read_bytes(),
        "q2_host_kernel_facts.py": b"# synthetic kernel reader\n",
        "q2_reconciliation_io.py": b"# synthetic held I/O\n",
    }
    docs = {"docs/local/A.md": b"synthetic local A\n", "docs/kernel/A.md": b"synthetic kernel A\n",
        "docs/local/B.md": b"synthetic local B\n", "docs/kernel/B.md": b"synthetic kernel B\n", "AGENTS.md": b"synthetic C ledger\n"}
    initial_files = dict(docs, **{"tests/e3_host/" + name: raw for name, raw in shared.items()})
    initial_tree = tree(initial_files)
    ka = commit(initial_tree, None, "kernel A")
    kc = commit(initial_tree, ka, "kernel C")
    old = [commit(initial_tree, kc, "old C one")]
    old.append(commit(initial_tree, old[-1], "old C two"))
    old.append(commit(initial_tree, old[-1], "old C three"))
    a = commit(initial_tree, old[-1], "local A")
    c = commit(initial_tree, a, "local C")
    authority = dict(rule=value.RULE, baseline=a, closure=c, owner_decision="synthetic-owner", scope="synthetic-scope")
    monkeypatch.setattr(value, "BASELINE", a)
    monkeypatch.setattr(value, "CLOSURE", c)
    monkeypatch.setattr(value, "KERNEL_A", ka)
    monkeypatch.setattr(value, "KERNEL_C", kc)
    monkeypatch.setattr(value, "CLOSURES", (*old, kc, c))
    monkeypatch.setattr(value, "AUTHORITY", authority)
    pins = {
        "authority/local/A.md": (a, "docs/local/A.md", value.sha(docs["docs/local/A.md"])),
        "authority/kernel/A.md": (ka, "docs/kernel/A.md", value.sha(docs["docs/kernel/A.md"])),
        "authority/local/B.md": (c, "docs/local/B.md", value.sha(docs["docs/local/B.md"])),
        "authority/kernel/B.md": (kc, "docs/kernel/B.md", value.sha(docs["docs/kernel/B.md"])),
        "authority/local/C_AGENTS.md": (c, "AGENTS.md", value.sha(docs["AGENTS.md"])),
        "authority/kernel/C_AGENTS.md": (kc, "AGENTS.md", value.sha(docs["AGENTS.md"])),
    }
    monkeypatch.setattr(value, "AUTHORITY_FILES", pins)
    monkeypatch.setattr(value, "RULE_SHA256", value.sha(b"synthetic rule\n"))
    sources = {"sources/" + key: ("synthetic inert " + key).encode() for key in "PMT"}
    monkeypatch.setattr(value, "SOURCES", {name: (len(raw), value.sha(raw)) for name, raw in sources.items()})
    contract = "\n".join(name + " = " + repr(authority[key]) for name, key in
        (("RULE", "rule"), ("BASELINE", "baseline"), ("CLOSURE", "closure"), ("OWNER_DECISION", "owner_decision"), ("SCOPE", "scope")))
    contract += '\ndef targets(*sources):\n    return {"targets": list(range(11)), "target_manifest_sha256": "' + "f" * 64 + '"}\n'
    observer = 'def run_local(*sources, reception_window, binding):\n    return ' + repr(dict(status="OBSERVED_PARTIAL", **{name: False for name in value.FALSE_FIELDS})) + ' | {"reception_window": reception_window, "binding": binding}\n'
    tools = dict(shared, **{"q2_local_source_contract.py": contract.encode(),
        "q2_local_source_observe.py": observer.encode(), "q2_local_source_delivery.py": SOURCE.read_bytes()})
    d_tree = tree(dict(docs, **{"tests/e3_host/" + name: raw for name, raw in tools.items()}))
    d = commit(d_tree, c, "D implementation")
    proof = dict(schema="q2-local-source-git-proof/v1", implementation_commit=d, implementation_tree=d_tree,
        required_closures=list(value.CLOSURES), objects=objects)
    package = dict(schema="q2-local-source-private-package/v1", authority=authority, implementation_commit=d,
        implementation_tree=d_tree, tools=list(value.TOOLS), field_delivery="RAM_RECEIVER_ONLY", allow_run=False, allow_consume=False)
    files = dict(sources, **{"authority/rule.md": b"synthetic rule\n", "package.json": value.encoded(package),
        "git-proof.json": value.encoded(proof)})
    files.update({name: docs[path] for name, (_, path, _) in pins.items()})
    files.update({"tools/" + name: raw for name, raw in tools.items()})
    return value, files, d, d_tree, tree, commit, objects


def test_genuine_git_graph_offline_check_has_no_field_reads(synthetic):
    value, files, d, d_tree, *_ = synthetic
    report = value.run_package(archive(value, files), "--check-offline", expected_commit=d, expected_tree=d_tree)
    assert report["status"] == "OFFLINE_CHECK_PASS" and report["target_count"] == 11
    assert report["field_reads_performed"] is False and report["ready"] is False
    assert report["git"]["tools_verified_before_execution"] is True


@pytest.mark.parametrize("member,reason", [
    ("tools/q2_local_source_contract.py", "TOOL_GIT_BLOB"),
    ("authority/local/A.md", "AUTHORITY_DIGEST"),
    ("sources/P", "FIXED_SOURCE_PIN"),
    ("authority/rule.md", "RULE_PIN"),
])
def test_rebuilt_index_cannot_adopt_changed_source_before_first_compile(synthetic, monkeypatch, member, reason):
    value, files, d, d_tree, *_ = synthetic
    files[member] += b"\n# changed with an honestly rebuilt package index\n"
    monkeypatch.setattr(value, "compile", lambda *_args: pytest.fail("unverified package reached compilation"), raising=False)
    with pytest.raises(ValueError, match=reason):
        value.run_package(archive(value, files), "--check-offline", expected_commit=d, expected_tree=d_tree)


def test_self_reported_commit_tree_cannot_replace_external_pin(synthetic):
    value, files, d, d_tree, *_ = synthetic
    with pytest.raises(ValueError, match="PACKAGE_IDENTITY"):
        value.run_package(archive(value, files), "--check-offline", expected_commit="a" * 40, expected_tree=d_tree)
    with pytest.raises(ValueError, match="GIT_HASH"):
        proof = value.document(files["git-proof.json"])
        proof["objects"][d]["data"] = base64.b64encode(b"tree " + d_tree.encode() + b"\n\nforged").decode()
        value._verify_git(proof, files, d, d_tree)


def test_missing_ancestor_and_changed_shared_tool_block_even_with_honest_new_d(synthetic):
    value, files, d, d_tree, tree, commit, all_objects = synthetic
    proof = value.document(files["git-proof.json"])
    proof["objects"].pop(value.CLOSURE)
    with pytest.raises(ValueError, match="C_ANCESTRY"):
        value._verify_git(proof, files, d, d_tree)
    # Changing a shared helper and naming its honest Git commit still violates C.
    files["tools/q2_host_kernel_facts.py"] += b"# unauthorized shared change\n"
    new_files = {path: files[name] for name, (_, path, _) in value.AUTHORITY_FILES.items()}
    new_files.update({"tests/e3_host/" + name: files["tools/" + name] for name in value.TOOLS})
    new_tree = tree(new_files)
    new_d = commit(new_tree, value.CLOSURE, "changed shared helper")
    proof = value.document(files["git-proof.json"])
    proof.update(implementation_commit=new_d, implementation_tree=new_tree, objects=all_objects)
    with pytest.raises(ValueError, match="SHARED_TOOL_CHANGED"):
        value._verify_git(proof, files, new_d, new_tree)


def test_transport_cannot_reset_origin_or_omit_startup_budget(synthetic, monkeypatch):
    value, files, d, d_tree, *_ = synthetic
    raw = archive(value, files)
    with pytest.raises(ValueError, match="ORIGIN_REQUIRED"):
        value.run_package(raw, "--local-source-evidence", expected_commit=d, expected_tree=d_tree)
    window = dict(issued_ns=1, deadline_ns=300000000001, boottime_issued_ns=1, boottime_deadline_ns=300000000001)
    monkeypatch.setattr(value.time, "monotonic_ns", lambda: 2)
    monkeypatch.setattr(value.time, "clock_gettime_ns", lambda _: 2)
    transport = dict(receiver_source_sha256=value.sha(files["tools/q2_local_source_delivery.py"]), receiver_command_bytes=200,
        frame_bytes=300, payload_input_bytes=300, package_bytes=len(raw), package_sha256=value.sha(raw))
    with pytest.raises(ValueError, match="INPUT_LIMIT"):
        value.run_package(raw, "--local-source-evidence", expected_commit=d, expected_tree=d_tree,
            reception_window=window, transport=transport)
    transport["payload_input_bytes"] = 500
    transport["receiver_source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="TRANSPORT_BINDING"):
        value.run_package(raw, "--local-source-evidence", expected_commit=d, expected_tree=d_tree,
            reception_window=window, transport=transport)


@pytest.mark.parametrize("mode", ["--execute", "--consume", "--local-preflight", "--local-source-evidence --run"])
def test_no_execution_entry(mode):
    with pytest.raises(ValueError, match="MODE"):
        module().run_package(b"not a package", mode, expected_commit="a" * 40, expected_tree="b" * 40)


def test_unindexed_or_duplicate_member_is_rejected(synthetic):
    value, files, *_ = synthetic
    raw = archive(value, dict(files, **{"__main__.py": b"raise AssertionError('never execute')"}))
    with pytest.raises(ValueError, match="PACKAGE_MEMBERS"):
        value._read_package(raw)
    buffer = io.BytesIO(archive(value, files))
    with zipfile.ZipFile(buffer, "a") as z:
        with pytest.warns(UserWarning, match="Duplicate name"):
            z.writestr("sources/P", files["sources/P"])
    with pytest.raises(ValueError, match="PACKAGE_MEMBERS"):
        value._read_package(buffer.getvalue())


def run_tty(payload, *, digest=None, message=None):
    value = module()
    digest = value.sha(payload) if digest is None else digest
    master, slave = pty.openpty()
    before = termios.tcgetattr(slave)
    proc = subprocess.Popen([sys.executable, "-I", "-B", "-S", "-c", SOURCE.read_text(),
        digest, str(len(payload)), "a" * 40, "b" * 40], stdin=slave, stdout=slave, stderr=slave)
    captured, sent = bytearray(), False
    until = time.monotonic() + 8
    try:
        while time.monotonic() < until:
            if select.select([master], [], [], 0.1)[0]:
                captured.extend(os.read(master, 65536))
            if not sent and b"Q2_LOCAL_SOURCE_RAM_READY" in captured:
                assert not termios.tcgetattr(slave)[3] & termios.ECHO
                frame = value.frame_bytes(payload) if message is None else message
                if digest != value.sha(payload) and message is None:
                    frame = frame.replace(value.sha(payload).encode(), digest.encode(), 1)
                for n in range(0, len(frame), 1024):
                    os.write(master, frame[n:n + 1024])
                sent = True
            if proc.poll() is not None:
                while select.select([master], [], [], 0)[0]:
                    captured.extend(os.read(master, 65536))
                break
        else:
            pytest.fail("receiver did not finish in the test bound")
        assert sent and termios.tcgetattr(slave) == before
        report = json.loads(next(line for line in reversed(captured.splitlines()) if line.startswith(b"{")))
        assert b"#Q2-LOCAL-SOURCE-EVIDENCE" not in captured
        assert len(captured) <= value.REPORT_LIMIT
        return proc.returncode, report
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
        os.close(master)
        os.close(slave)


def test_actual_pty_frame_counts_and_terminal_restore_before_untrusted_zip():
    payload = b"inert non-zip package"
    code, report = run_tty(payload)
    assert code == 2 and "BadZipFile" in report["reason"]
    value = module()
    wire = value.frame_bytes(payload)
    transport = report["transport"]
    assert transport["frame_bytes"] == len(wire)
    command = value.command_bytes(SOURCE.read_bytes(), value.sha(payload), len(payload), "a" * 40, "b" * 40)
    assert transport["payload_input_bytes"] == len(command) + len(wire)
    assert report["delivery_output"]["emitted_stderr_bytes"] == 0


def test_actual_pty_wrong_hash_never_executes_payload(tmp_path):
    marker = tmp_path / "must-not-be-created"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("__main__.py", "from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n")
    code, report = run_tty(buffer.getvalue(), digest="0" * 64)
    assert code == 2 and "PACKAGE_PIN" in report["reason"] and not marker.exists()


@pytest.mark.parametrize("body", [b"not-a-comment\n", b"#!!!!\n", b"#" + b"A" * 1025 + b"\n"])
def test_actual_pty_rejects_bad_frame_and_restores_terminal(body):
    value = module()
    payload = b"inert bytes"
    frame = value.HEADER + value.sha(payload).encode() + b"\n" + body
    code, report = run_tty(payload, message=frame)
    assert code == 2 and report["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED"


def test_receiver_checks_boottime_before_available_input(monkeypatch):
    value = module()
    window = dict(issued_ns=1, deadline_ns=300000000001, boottime_issued_ns=1, boottime_deadline_ns=300000000001)
    monkeypatch.setattr(value.time, "monotonic_ns", lambda: 2)
    monkeypatch.setattr(value.time, "clock_gettime_ns", lambda _: 140000000001)
    monkeypatch.setattr(value.os, "read", lambda *_: pytest.fail("expired receiver read input"))
    with pytest.raises(ValueError, match="PREPARATION_EXPIRED"):
        value._frame(0, 1, "0" * 64, window, {})


def test_receiver_counts_command_before_frame_limit(monkeypatch):
    value = module()
    monkeypatch.setattr(value, "_remaining", lambda *_: 1)
    monkeypatch.setattr(value.select, "select", lambda *_: ([0], [], []))
    monkeypatch.setattr(value.os, "read", lambda *_: b"123")
    transport = dict(frame_bytes=0, receiver_command_bytes=value.INPUT_LIMIT - 2)
    with pytest.raises(ValueError, match="INPUT_LIMIT"):
        value._frame(0, 1, "0" * 64, {}, transport)


def test_final_output_count_is_fixed_point_and_reserves_joint_diagnostics():
    value = module()
    report = dict(status="OBSERVED_PARTIAL", byte_counts=dict(output_json_bytes=0))
    raw = value._response(report, len(value.READY))
    result = value.document(raw)
    assert result["byte_counts"]["output_json_bytes"] == result["delivery_output"]["report_serialized_bytes"] == len(raw)
    assert result["delivery_output"]["complete_stdout_bytes"] == len(raw) + len(value.READY)
    assert report["byte_counts"]["output_json_bytes"] == 0
    with pytest.raises(ValueError, match="REPORT_LIMIT"):
        value._response(dict(data="x" * value.REPORT_LIMIT), len(value.READY))


def test_encoding_cannot_refresh_receiver_origin(monkeypatch):
    value = module()
    window = dict(issued_ns=1, deadline_ns=300000000001, boottime_issued_ns=1, boottime_deadline_ns=300000000001)
    monkeypatch.setattr(value.time, "monotonic_ns", lambda: 2)
    boot = iter((2, 140000000001))
    monkeypatch.setattr(value.time, "clock_gettime_ns", lambda _: next(boot))
    with pytest.raises(ValueError, match="PREPARATION_EXPIRED"):
        value._response(dict(status="OBSERVED_PARTIAL"), 0, window)


def test_output_expiry_restores_descriptor_flags(monkeypatch):
    value = module()
    before = value.fcntl.fcntl(1, value.fcntl.F_GETFL)
    window = dict(issued_ns=1, deadline_ns=300000000001, boottime_issued_ns=1, boottime_deadline_ns=300000000001)
    monkeypatch.setattr(value.time, "monotonic_ns", lambda: 300000000001)
    monkeypatch.setattr(value.time, "clock_gettime_ns", lambda _: 2)
    monkeypatch.setattr(value.os, "write", lambda *_: pytest.fail("expired receiver emitted output"))
    with pytest.raises(ValueError, match="OUTPUT_EXPIRED"):
        value._write_result(b"bounded report", window)
    assert value.fcntl.fcntl(1, value.fcntl.F_GETFL) == before


def test_valid_transport_passes_the_original_window_without_sampling_a_new_origin(synthetic, monkeypatch):
    value, files, d, d_tree, *_ = synthetic
    raw = archive(value, files)
    window = dict(issued_ns=1, deadline_ns=300000000001, boottime_issued_ns=1, boottime_deadline_ns=300000000001)
    monkeypatch.setattr(value.time, "monotonic_ns", lambda: 2)
    monkeypatch.setattr(value.time, "clock_gettime_ns", lambda _: 2)
    monkeypatch.setattr(value, "_window", lambda: pytest.fail("sampled a new receiver origin"))
    transport = dict(receiver_source_sha256=value.sha(files["tools/q2_local_source_delivery.py"]),
        receiver_command_bytes=200, frame_bytes=300, payload_input_bytes=500,
        package_bytes=len(raw), package_sha256=value.sha(raw))
    result = value.run_package(raw, "--local-source-evidence", expected_commit=d, expected_tree=d_tree,
        reception_window=window, transport=transport)
    assert result["reception_window"] == window
    assert result["binding"]["transport"] == transport


def test_unexpired_dual_clocks_must_not_diverge(monkeypatch):
    value = module()
    window = dict(issued_ns=1, deadline_ns=300000000001, boottime_issued_ns=1, boottime_deadline_ns=300000000001)
    monkeypatch.setattr(value.time, "monotonic_ns", lambda: 2)
    monkeypatch.setattr(value.time, "clock_gettime_ns", lambda _: 3000000002)
    with pytest.raises(ValueError, match="CLOCK_DIVERGED"):
        value._remaining(window)


def test_output_limit_failure_retains_measured_scope_but_omits_raw():
    value = module()
    report = dict(status="OBSERVED_PARTIAL", phase="final_local_recheck",
        completion=dict(attempted=11, observed=11, matched=11, raw_returned=4),
        byte_counts=dict(payload_input=6000000, ordinary_actual_read=10490352,
            kernel_actual_read=5000, output_json_bytes=0), raw_base64="x" * value.REPORT_LIMIT)
    with pytest.raises(ValueError, match="REPORT_LIMIT"):
        value._response(report, len(value.READY))
    blocked = value._blocked("LOCAL_DELIVERY_REPORT_LIMIT", prior=report,
        expected_commit="a" * 40, expected_tree="b" * 40)
    result = value.document(value._response(blocked, len(value.READY)))
    assert result["completion"] == dict(attempted=11, observed=11, matched=11, raw_returned=0, expected_objects=11)
    assert result["raw_omitted_after_delivery_failure"] == 4 and "raw_base64" not in result
    assert result["byte_counts"]["ordinary_actual_read"] == 10490352
    assert result["byte_counts"]["kernel_actual_read"] == 5000
    assert result["phase"] == "final_local_recheck"
    assert result["authority"] == value.AUTHORITY and result["implementation_commit"] == "a" * 40
    assert result["byte_counts"]["output_json_bytes"] == result["delivery_output"]["report_serialized_bytes"]
    assert result["status"] == "LOCAL_SOURCE_EVIDENCE_BLOCKED" and result["allow_consume"] is False
    repeated = value._blocked("LOCAL_DELIVERY_PREPARATION_EXPIRED", prior=result)
    assert repeated["raw_omitted_after_delivery_failure"] == 4
    assert repeated["byte_counts"]["ordinary_actual_read"] == 10490352
