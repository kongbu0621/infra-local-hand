"""Real local pipes and expiry cases; no SSH or guest execution."""
import hashlib
import base64
import gzip
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time

import pytest

from e3_host import q2_host_window_delivery as d


# Contract-only cases use a synthetic identity and clock. Real transport tests
# opt into Linux before reading procfs or using BOOTTIME/process-group syscalls.
BOOT = "12345678-1234-1234-1234-123456789abc"
linux_transport = pytest.mark.skipif(not sys.platform.startswith("linux"),
    reason="Linux procfs, BOOTTIME and process-group pipe transport")


def host_boot():
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def capture(script, callback, *, duration=3, prior=0, argv=None, output_limit=None):
    window = d.base.Window()
    loader = d.framed_loader(boot_id=host_boot(),
        deadline_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME) + int(duration * d.NS))
    return d.capture_framed_memory(argv or [sys.executable, "-I", "-B", "-c", loader], script,
        window=window, until_ns=window.issued_ns + int(duration * d.NS),
        prior_bytes=prior, output_limit=output_limit, on_stdout_line=callback)


SCRIPT = b"import os,select\nassert not select.select([0],[],[],0)[0]\nprint('LIVE',flush=True)\nassert os.read(0,16384)==b'ACK\\n'\nassert os.read(0,1)==b''\nprint('DONE',flush=True)\n"


@linux_transport
def test_ack_follows_complete_script_and_stdin_stays_open_until_ack():
    seen = []
    def callback(line):
        seen.append(line)
        return b"ACK\n" if line == b"LIVE\n" else None
    result = capture(SCRIPT, callback)
    assert result["record"]["complete"]
    assert seen == [b"LIVE\n", b"DONE\n"]
    assert result["record"]["ack_delivered"]
    assert result["record"]["input_bytes_sent"] == 9 + len(SCRIPT) + 4
    assert result["record"]["remote_stop_proven"] is False
    assert result["record"]["q2_accepted"] is False


@linux_transport
def test_missing_ack_neither_closes_input_nor_renews_time():
    started = time.monotonic()
    result = capture(SCRIPT, lambda _: None, duration=.3)
    assert time.monotonic() - started < 2
    assert not result["record"]["complete"]
    assert result["record"]["error"] == "HOST_WINDOW_CAPTURE_TIMEOUT"
    assert result["record"]["ack_delivered"] is False
    assert result["record"]["remote_stop_proven"] is False


@linux_transport
@pytest.mark.parametrize("ack", [b"x", b"x\ny\n", b"x" * d.ACK_LIMIT + b"\n", "ACK\n"])
def test_ack_requires_one_bounded_binary_line(ack):
    result = capture(SCRIPT, lambda _: ack)
    assert result["record"]["error"] == "HOST_WINDOW_ACK_FRAME"
    assert not result["record"]["ack_delivered"]


@linux_transport
def test_second_ack_cannot_authorize_a_second_phase():
    result = capture(b"print('LIVE',flush=True)\nimport os\nos.read(0,16384)\nprint('LIVE',flush=True)\n",
        lambda _: b"ACK\n")
    assert result["record"]["error"] == "HOST_WINDOW_ACK_REPEATED"
    assert result["record"]["complete"] is False


@linux_transport
def test_ack_before_script_is_fully_delivered_is_rejected():
    command = "import time;print('LIVE',flush=True);time.sleep(5)"
    result = capture(b"#" + b"x" * (1024 * 1024), lambda _: b"ACK\n",
        argv=[sys.executable, "-I", "-B", "-c", command])
    assert result["record"]["error"] == "HOST_WINDOW_ACK_BEFORE_FRAME"


@linux_transport
def test_callback_failure_is_retained_and_never_grants_ack():
    def refused(_): raise ValueError("HOST_HISTORY_CHANGED")
    result = capture(SCRIPT, refused)
    assert result["record"]["error"] == "HOST_HISTORY_CHANGED"
    assert not result["record"]["ack_delivered"]


@linux_transport
def test_original_output_pool_includes_all_phases():
    result = capture(b"print('x'*4096,flush=True)\n", lambda _: None,
        prior=d.OUTPUT_LIMIT - 256)
    assert result["record"]["error"] == "HOST_WINDOW_CAPTURE_LIMIT"
    assert result["record"]["total_captured_bytes"] == d.OUTPUT_LIMIT


@linux_transport
def test_guest_loader_refuses_expired_before_reading_any_input():
    source = d.framed_loader(boot_id=host_boot(), deadline_ns=1)
    process = subprocess.Popen([sys.executable, "-I", "-B", "-c", source],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert process.wait(timeout=2) != 0
        assert b"HOST_WINDOW_LOADER_EXPIRED" in process.stderr.read()
    finally:
        process.stdin.close(); process.stdout.close(); process.stderr.close()


@linux_transport
def test_guest_ack_expiry_precedes_read():
    read, write = os.pipe()
    try:
        os.write(write, b"ACK\n")
        with pytest.raises(ValueError, match="ACK_EXPIRED"):
            d.read_ack(boot_id=host_boot(), deadline_ns=1, fd=read)
        assert os.read(read, 4) == b"ACK\n"
    finally:
        os.close(read); os.close(write)


@linux_transport
def test_guest_ack_eof_is_not_ack():
    read, write = os.pipe(); os.close(write)
    try:
        with pytest.raises(ValueError, match="ACK_EOF"):
            d.read_ack(boot_id=host_boot(), deadline_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME) + d.NS, fd=read)
    finally:
        os.close(read)


@linux_transport
def test_memory_wrapper_executes_pinned_text_without_reading_source_file(tmp_path):
    source = b"#!/bin/sh\nprintf '%s\\n' \"$1\"\n"
    path = tmp_path / "wrapper.sh"
    path.write_bytes(source); path.chmod(0o700)
    before = path.stat()
    args = d.memory_wrapper_argv(source, expected_sha256=hashlib.sha256(source).hexdigest(),
        wrapper_path=str(path), remote_argv=["fixed-command", "two words"])
    process = subprocess.run(args, check=True, capture_output=True)
    assert process.stdout == b"fixed-command 'two words'\n"
    after = path.stat()
    assert before == after
    assert before.st_atime_ns == after.st_atime_ns


@pytest.mark.parametrize("source", [b"#!/usr/bin/python3\npass\n", b"#!/bin/bash\ncat $0\n",
    b"#!/bin/bash\necho ${BASH_SOURCE[0]}\n"])
def test_unknown_wrapper_semantics_are_not_guessed(source, monkeypatch):
    # Model Linux wrapper lexical paths only; this case performs no filesystem
    # operation and does not claim native Windows wrapper execution support.
    monkeypatch.setattr(d, "Path", PurePosixPath)
    with pytest.raises(ValueError, match="WRAPPER_(INTERPRETER|FILE_SEMANTICS)_UNSUPPORTED"):
        d.memory_wrapper_argv(source, expected_sha256=hashlib.sha256(source).hexdigest(),
            wrapper_path="/known/wrapper.sh", remote_argv=["fixed"])


def test_unbound_wrapper_environment_is_not_silently_changed(monkeypatch):
    # Exercise the parser beyond its Linux-path boundary on every CI platform.
    monkeypatch.setattr(d, "Path", PurePosixPath)
    source = b'#!/bin/sh\nexec ssh "$REMOTE_HOST" "$@"\n'
    with pytest.raises(ValueError, match="WRAPPER_ENVIRONMENT_UNSUPPORTED"):
        d.memory_wrapper_argv(source, expected_sha256=hashlib.sha256(source).hexdigest(),
            wrapper_path="/known/wrapper.sh", remote_argv=["fixed"])


def test_frame_limit_reserves_the_ack_and_header():
    window = d.base.Window(monotonic=lambda: 100 * d.NS, boottime=lambda: 100 * d.NS)
    with pytest.raises(ValueError, match="FRAME_LIMIT"):
        d.capture_framed_memory([sys.executable], b"x" * d.INPUT_LIMIT,
            window=window, until_ns=window.deadline_ns, on_stdout_line=lambda _: None)


def test_whole_config_compression_preserves_exact_fields_and_limits():
    config = {"archive": "a" * (18 * 1024**2), "fields": {"ready": False, "number": 10}}
    packed = d.pack_config(config)
    assert packed["decoded_bytes"] > d.INPUT_LIMIT
    assert len(packed["data"]) < d.INPUT_LIMIT
    assert d.unpack_config(packed) == config
    source = d.config_loader_source(config)
    loaded = {}
    exec(compile(source, "<local-config-loader-test>", "exec"), loaded)
    assert loaded["_bootstrap_config"] == config
    assert len(source.encode()) + d.HEADER_BYTES + d.ACK_LIMIT <= d.INPUT_LIMIT


def test_config_decoded_size_bound_is_enforced_before_unbounded_inflate():
    packed = d.pack_config({"large": "x" * 100000})
    packed["decoded_bytes"] = 32
    with pytest.raises(ValueError, match="CONFIG_CONTENT"):
        d.unpack_config(packed)
    packed["decoded_bytes"] = d.CONFIG_LIMIT + 1
    with pytest.raises(ValueError, match="CONFIG_LIMIT"):
        d.unpack_config(packed)


def test_config_rejects_trailing_members_wrong_hash_and_ambiguous_json():
    packed = d.pack_config({"value": 1})
    compressed = base64.b64decode(packed["data"])
    packed["data"] = base64.b64encode(compressed + gzip.compress(b"{}")).decode()
    with pytest.raises(ValueError, match="CONFIG_CONTENT"):
        d.unpack_config(packed)
    packed = d.pack_config({"value": 1}); packed["decoded_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="CONFIG_CONTENT"):
        d.unpack_config(packed)
    raw = b'{"value":1,"value":2}'
    packed.update(decoded_bytes=len(raw), decoded_sha256=hashlib.sha256(raw).hexdigest(),
        data=base64.b64encode(gzip.compress(raw)).decode())
    with pytest.raises(ValueError, match="DUPLICATE_KEY"):
        d.unpack_config(packed)
    with pytest.raises(ValueError, match="JSON_NUMBER"):
        d.pack_config({"value": 1.5})


def test_environment_keeps_credential_discovery_without_shell_startup_injection():
    env = d.controlled_environment(dict(HOME="/known/home", SSH_AUTH_SOCK="/known/agent",
        BASH_ENV="/bad", ENV="/bad", PATH="/bad", BASH_FUNC_ssh="bad"))
    assert env["HOME"] == "/known/home" and env["SSH_AUTH_SOCK"] == "/known/agent"
    assert env["PATH"] == "/usr/bin:/bin"
    assert not {"BASH_ENV", "ENV", "BASH_FUNC_ssh"} & env.keys()


def test_absent_clock_evidence_fails_before_spawning_or_callback(monkeypatch):
    proof = d.remote_deadline_proof([], host_boot_id=BOOT, guest_boot_id=BOOT)
    assert proof["status"] == "BLOCKED" and proof["dispatch_allowed"] is False
    assert not proof["current_host_boot_bound"] and not proof["host_boottime_mapping_proven"]
    def forbidden(*args, **kwargs): raise AssertionError("must not spawn")
    monkeypatch.setattr(d.subprocess, "Popen", forbidden)
    window = d.base.Window(monotonic=lambda: 100 * d.NS, boottime=lambda: 100 * d.NS)
    with pytest.raises(ValueError, match="EXISTING_REMOTE_HARD_DEADLINE_UNPROVEN"):
        d.dispatch_original(["unknown"], b"pass", retained_anchors=[], host_boot_id=BOOT,
            guest_boot_id=BOOT, window=window, until_ns=window.deadline_ns, on_stdout_line=forbidden)


def test_self_asserted_admitted_flags_are_not_deadline_evidence():
    with pytest.raises(ValueError, match="RETAINED_CLOCKS"):
        d.require_remote_deadline({"status": "ADMITTED", "dispatch_allowed": True},
            host_boot_id=BOOT, guest_boot_id=BOOT)
    with pytest.raises(ValueError, match="RETAINED_CLOCK_PIN"):
        d.remote_deadline_proof([b'{"status":"ADMITTED"}'], host_boot_id=BOOT, guest_boot_id=BOOT)


def test_actual_historical_format_lacks_host_boot_and_boottime(monkeypatch):
    old = d.helper("q2_retry_delivery")
    anchor = old.make_clock_anchor(host_issued_ns=100*d.NS, host_deadline_ns=400*d.NS,
        host_probe_send_ns=110*d.NS, host_probe_receive_ns=112*d.NS, guest_boot_id=BOOT,
        expected_boot_id=BOOT, guest_sample_ns=1000*d.NS)
    raw = old.encoded(anchor)
    monkeypatch.setattr(d, "ANCHOR_PINS", {hashlib.sha256(raw).hexdigest(): len(raw)})
    proof = d.remote_deadline_proof([raw], host_boot_id=BOOT, guest_boot_id=BOOT)
    assert proof["clock_evidence"][0]["guest_boot_bound"]
    assert proof["clock_evidence"][0]["current_host_boot_bound"] is False
    assert proof["absolute_manager_deadline_proven"] is False
    assert proof["dispatch_allowed"] is False
