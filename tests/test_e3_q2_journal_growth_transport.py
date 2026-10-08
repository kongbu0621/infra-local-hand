"""Synthetic pipe peers exercise maintenance ordering, persistence and timeout."""
from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import zlib

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux maintenance transport", allow_module_level=True)

from e3_host import q2_journal_growth as h


BOOT = "10000000-0000-4000-8000-000000000001"
NEW_BOOT = "20000000-0000-4000-8000-000000000001"
NONCE, SHA = "1" * 64, "2" * 64


def report(phase="pre", **changes):
    value = dict(schema="lhq-journal-growth-guest/v2", session=h.SESSION, phase=phase,
                 nonce=NONCE, source_binding_sha256=SHA,
                 status="GUEST_QUIET" if phase == "pre" else "FILESYSTEM_GROWN",
                 boot_id=BOOT if phase == "pre" else NEW_BOOT)
    if phase == "post":
        value["original_boot_id"] = BOOT
    return value | changes


@pytest.fixture
def factory(tmp_path):
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOATIME)
    exe = os.open(sys.executable, os.O_PATH | os.O_CLOEXEC)
    store = h.Store(parent, lambda: None)
    transports = []
    def create(code, *, phase="pre", check=lambda: None, validate=None):
        def spawn(_argv, **kwargs):
            return subprocess.Popen([sys.executable, "-I", "-B", "-c", code], **kwargs)
        result = h.MaintenanceTransport(SimpleNamespace(ssh=exe), store, [sys.executable],
            phase, NONCE, SHA, BOOT, check, validate=validate, popen=spawn)
        transports.append(result)
        return result
    yield create, store, tmp_path
    for transport in transports:
        transport.close()
        # Synthetic peers always exit naturally or after their stdin closes.
        transport.process.wait(timeout=5)
    store.close()
    os.close(parent)
    os.close(exe)


def peer(value, suffix=""):
    return "import sys\nsys.stdout.buffer.write(" + repr(h.canonical(value)) + ");sys.stdout.flush()\n" + suffix


def test_pre_capture_durable_before_one_token_and_ack(factory):
    create, store, root = factory
    value = report()
    sha = h.digest(h.canonical(value))
    token = h.continue_token(NONCE, sha)
    ack = dict(schema="lhq-journal-growth-guest/v2", session=h.SESSION,
               status="POWER_OFF_REQUESTED", nonce=NONCE, pre_report_sha256=sha, guest_startup_assurance=h.guest_startup_assurance())
    code = peer(value, "token=sys.stdin.buffer.readline()\nassert token==" + repr(token) + "\n"
                "sys.stderr.buffer.write(b'peer stderr\\n');sys.stderr.flush()\n"
                "sys.stdout.buffer.write(" + repr(h.canonical(ack)) + ");sys.stdout.flush()\n")
    transport = create(code)
    assert transport.receive_report() == value
    assert (root / h.NAMES["pre.stdout"]).read_bytes() == h.canonical(value)
    transport.continue_poweroff(sha)
    with pytest.raises(h.prior.r.ObservationError, match="CONTINUE_BINDING"):
        transport.continue_poweroff(sha)
    result = transport.finish()
    assert result["ack"] == ack and result["returncode"] == 0 and all(result["eof"].values())
    assert (root / h.NAMES["pre.stdout"]).read_bytes() == h.canonical(value) + h.canonical(ack)
    assert (root / h.NAMES["pre.stderr"]).read_bytes() == b"peer stderr\n"
    assert b'"step":"POWER_OFF_TOKEN"' in (root / h.NAMES["events.jsonl"]).read_bytes()


@pytest.mark.parametrize("changes", [dict(nonce="3" * 64), dict(source_binding_sha256="4" * 64),
    dict(boot_id=NEW_BOOT), dict(phase="post"), dict(status="FILESYSTEM_GROWN"), dict(session="other")])
def test_unbound_pre_report_never_authorizes_token(factory, changes):
    create, _store, root = factory
    transport = create(peer(report(**changes)))
    with pytest.raises(h.prior.r.ObservationError):
        transport.receive_report()
    assert transport.sent is False
    assert not (root / h.NAMES["events.jsonl"]).exists()


def test_token_cannot_precede_report(factory):
    create, _store, _root = factory
    transport = create(peer(report()))
    with pytest.raises(h.prior.r.ObservationError, match="CONTINUE_BINDING"):
        transport.continue_poweroff(SHA)


def test_precondition_callback_can_reject_before_token(factory):
    create, _store, _root = factory
    transport = create(peer(report()), validate=lambda _: (_ for _ in ()).throw(ValueError("post too large")))
    with pytest.raises(ValueError, match="post too large"):
        transport.receive_report()
    assert not transport.sent


def test_post_uses_eof_and_requires_new_boot(factory):
    create, _store, root = factory
    value = report("post")
    transport = create("import sys\nassert sys.stdin.buffer.read()==b''\n" + peer(value), phase="post")
    assert transport.process.stdin is None
    assert transport.receive_report() == value
    assert transport.finish()["returncode"] == 0
    assert (root / h.NAMES["post.stdout"]).read_bytes() == h.canonical(value)


@pytest.mark.parametrize("suffix", ["sys.stdout.write('extra\\n');sys.stdout.flush()\n", "sys.exit(3)\n"])
def test_post_extra_output_or_nonzero_is_not_success(factory, suffix):
    create, _store, _root = factory
    transport = create(peer(report("post"), suffix), phase="post")
    transport.receive_report()
    with pytest.raises(h.prior.r.ObservationError, match="POST_RETURN"):
        transport.finish()


def test_deadline_retains_live_peer_and_partial_capture(factory):
    create, _store, root = factory
    expire = [False]
    def check():
        if expire[0]:
            raise TimeoutError("fixed deadline")
    transport = create(peer(report(), "import time\ntime.sleep(.3)\n"), check=check)
    transport.receive_report()
    expire[0] = True
    with pytest.raises(TimeoutError) as failure:
        transport.continue_poweroff(h.digest(h.canonical(report())))
    assert failure.value.growth_transport is transport
    assert transport.process.poll() is None
    assert (root / h.NAMES["pre.stdout"]).read_bytes() == h.canonical(report())


def test_exact_one_mebibyte_cap_preserves_prefix(factory):
    create, _store, root = factory
    transport = create("import sys\nsys.stdout.buffer.write(b'x'*(1048576+1));sys.stdout.flush()\n")
    with pytest.raises(h.prior.r.ObservationError, match="STREAM_LIMIT"):
        transport.receive_report()
    assert (root / h.NAMES["pre.stdout"]).stat().st_size == h.MIB


def test_memory_loader_only_executes_supplied_synthetic_modules():
    sources = {"q2_core_capacity_reader.py": b"VALUE=123\n",
               "q2_journal_growth_guest.py": b"from e3_host import q2_core_capacity_reader as r\ndef entry(raw):\n print(r.VALUE,raw.decode())\n return 0\n"}
    encoded, sha = h.source_bundle(sources, dict(test="synthetic"))
    result = subprocess.run([sys.executable, "-I", "-B", "-c", h.GUEST_LOADER, encoded, sha],
                            capture_output=True, timeout=5)
    assert result.returncode == 0 and result.stdout == b'123 {"test":"synthetic"}\n\n'
    command = h.remote_argv("/synthetic/anchor", sources, dict(test="synthetic"))
    assert command[-2] == "q1admin@127.0.0.1"
    assert command[-1].startswith("exec /usr/bin/sudo -n -- /usr/bin/env -i ")
    assert "ConnectionAttempts=1" in command and "ControlMaster=no" in command


def test_memory_loader_rejects_compressed_expansion():
    raw = zlib.compress(b"x" * 400000)
    result = subprocess.run([sys.executable, "-I", "-B", "-c", h.GUEST_LOADER,
                            base64.b64encode(raw).decode(), h.digest(raw)], capture_output=True, timeout=5)
    assert result.returncode != 0 and b"BUNDLE_BOUND" in result.stderr


def test_source_bundle_rejects_oversized_second_phase_before_any_ssh():
    sources = {"q2_core_capacity_reader.py": b"# synthetic", "q2_journal_growth_guest.py": b"# synthetic"}
    with pytest.raises(h.prior.r.ObservationError, match="BUNDLE_INPUT"):
        h.source_bundle(sources, dict(pre_report="x" * 65536))
