"""Actual PTY framing preserves terminal state and rejects bytes before exec."""
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
import sys
import termios
import time
import zipfile

import pytest

SOURCE = Path(__file__).parent / "e3_host/q2_host_window_receiver.py"


def package(source):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("__main__.py", source)
    return stream.getvalue()


def frame(raw, expected):
    data = base64.b64encode(raw)
    return (("#Q2-LOCAL-PREFLIGHT " + expected + "\n").encode()
        + b"".join(b"#" + data[n:n + 1024] + b"\n" for n in range(0, len(data), 1024))
        + b"#END-Q2-LOCAL-PREFLIGHT\n")


def run_tty(payload, expected, *, message=None, size=None):
    master, slave = pty.openpty()
    before = termios.tcgetattr(slave)
    proc = subprocess.Popen([sys.executable, "-I", "-B", "-S", "-u", "-c", SOURCE.read_text(),
        expected, str(len(payload) if size is None else size)], stdin=slave, stdout=slave, stderr=slave)
    captured = bytearray()
    until = time.monotonic() + 8
    sent = False
    try:
        while time.monotonic() < until:
            readable, _, _ = select.select([master], [], [], 0.1)
            if readable:
                captured.extend(os.read(master, 65536))
            if not sent and b"Q2_RAM_READY" in captured:
                assert not termios.tcgetattr(slave)[3] & termios.ECHO
                raw = frame(payload, expected) if message is None else message
                for n in range(0, len(raw), 1024):
                    os.write(master, raw[n:n + 1024])
                sent = True
            if proc.poll() is not None:
                while select.select([master], [], [], 0)[0]:
                    captured.extend(os.read(master, 65536))
                break
        else:
            pytest.fail("receiver did not exit within test bound")
        assert sent
        assert termios.tcgetattr(slave) == before
        lines = bytes(captured).splitlines()
        assert len(captured) < 2 * 1024**2
        return proc.returncode, json.loads(next(line for line in reversed(lines) if line.startswith(b"{"))), bytes(captured)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
        os.close(master)
        os.close(slave)


def test_actual_pty_ram_delivery_and_origin(tmp_path):
    raw = package('''def run_package(raw, mode, *, reception_window):
    import time
    assert mode == "--local-preflight"
    assert reception_window["issued_ns"] <= time.monotonic_ns()
    assert reception_window["deadline_ns"] - reception_window["issued_ns"] == 300000000000
    return dict(status="OBSERVED_PARTIAL", ready=False, execution_window_consumed=False)
''')
    prior = list(tmp_path.iterdir())
    code, report, output = run_tty(raw, hashlib.sha256(raw).hexdigest())
    assert code == 0 and report["status"] == "OBSERVED_PARTIAL" and report["ready"] is False
    assert b"#Q2-LOCAL-PREFLIGHT" not in output  # no payload echo
    assert list(tmp_path.iterdir()) == prior


def test_wrong_package_hash_never_executes(tmp_path):
    marker = tmp_path / "must-not-be-created"
    raw = package("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n")
    code, report, _ = run_tty(raw, "0" * 64)
    assert code == 2 and "PACKAGE_PIN" in report["reason"]
    assert not marker.exists()


@pytest.mark.parametrize("body", [b"not-a-comment\n", b"#!!!!\n", b"#" + b"A" * 1025 + b"\n"])
def test_bad_frame_refused_and_terminal_restored(body):
    raw = package("raise AssertionError('not reachable')\n")
    expected = hashlib.sha256(raw).hexdigest()
    message = ("#Q2-LOCAL-PREFLIGHT " + expected + "\n").encode() + body
    code, report, _ = run_tty(raw, expected, message=message)
    assert code == 2 and report["status"] == "LOCAL_PREFLIGHT_BLOCKED"
    assert "not reachable" not in report["reason"]


def test_oversize_output_returns_bounded_block():
    raw = package('''def run_package(raw, mode, *, reception_window):
    return dict(status="OBSERVED_PARTIAL", data="a" * (2 * 1024**2))
''')
    code, report, _ = run_tty(raw, hashlib.sha256(raw).hexdigest())
    assert code == 2 and report["reason"] == "RAM_RECEIVER_OUTPUT_LIMIT"


def test_boottime_expiry_prevents_reading_even_available_input(monkeypatch):
    spec = importlib.util.spec_from_file_location("_receiver_deadline_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    window = dict(issued_ns=1, deadline_ns=300000000001,
        boottime_issued_ns=1, boottime_deadline_ns=300000000001)
    monkeypatch.setattr(module.time, "monotonic_ns", lambda: 2)
    monkeypatch.setattr(module.time, "clock_gettime_ns", lambda _clock: 140000000001)
    monkeypatch.setattr(module.os, "read", lambda *_args: pytest.fail("expired receiver read input"))
    with pytest.raises(ValueError, match="PREPARATION_EXPIRED"):
        module._frame(0, 1, "0" * 64, window)


def test_output_expiry_restores_descriptor_flags(monkeypatch):
    spec = importlib.util.spec_from_file_location("_receiver_output_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = module.fcntl.fcntl(1, module.fcntl.F_GETFL)
    window = dict(issued_ns=1, deadline_ns=300000000001,
        boottime_issued_ns=1, boottime_deadline_ns=300000000001)
    monkeypatch.setattr(module.time, "monotonic_ns", lambda: 300000000001)
    monkeypatch.setattr(module.time, "clock_gettime_ns", lambda _clock: 2)
    monkeypatch.setattr(module.os, "write", lambda *_args: pytest.fail("expired receiver wrote output"))
    with pytest.raises(ValueError, match="OUTPUT_EXPIRED"):
        module._write_result(b"bounded report", window)
    assert module.fcntl.fcntl(1, module.fcntl.F_GETFL) == before
