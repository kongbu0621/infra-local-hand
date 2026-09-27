"""Bounded RAM input for the already approved local-only host preflight.

The private delivery embeds these exact Git bytes in a short ``python -c``
command, with the exact package size and SHA-256 as arguments. No shell heredoc,
host download, archive extraction, remote command or persistent result is used.
The receiver's earlier clocks cover reception, verification and observation.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import io
import json
import os
import re
import select
import signal
import sys
import termios
import time
import zipfile

INPUT_LIMIT = 16 * 1024**2
OUTPUT_LIMIT = 2 * 1024**2
LINE_LIMIT = 1026
END = b"#END-Q2-LOCAL-PREFLIGHT\n"
READY = b"Q2_RAM_READY: paste the complete # frame now\n"


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def _window():
    boot = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    mono = time.monotonic_ns()
    return dict(issued_ns=mono, deadline_ns=mono + 300 * 10**9,
        boottime_issued_ns=boot, boottime_deadline_ns=boot + 300 * 10**9)


def _remaining(window):
    mono, boot = time.monotonic_ns(), time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    require(mono >= window["issued_ns"] and boot >= window["boottime_issued_ns"],
        "RAM_RECEIVER_CLOCK_REVERSED")
    left = min(window["issued_ns"] + 140 * 10**9 - mono,
        window["boottime_issued_ns"] + 140 * 10**9 - boot)
    require(left > 0, "RAM_RECEIVER_PREPARATION_EXPIRED")
    return left / 10**9


def _frame(fd, expected_size, expected_sha, window):
    """Each complete frame line is a shell comment if pasted in the wrong place."""
    header = ("#Q2-LOCAL-PREFLIGHT " + expected_sha + "\n").encode("ascii")
    pending, decoded = bytearray(), bytearray()
    received, first = 0, True
    while True:
        ready, _, _ = select.select([fd], [], [], _remaining(window))
        require(ready, "RAM_RECEIVER_INPUT_TIMEOUT")
        chunk = os.read(fd, LINE_LIMIT)
        require(chunk, "RAM_RECEIVER_INPUT_EOF")
        received += len(chunk)
        # The private builder also counts the command and all framing bytes.
        require(received <= INPUT_LIMIT, "RAM_RECEIVER_INPUT_LIMIT")
        pending.extend(chunk)
        while b"\n" in pending:
            index = pending.index(b"\n")
            line = bytes(pending[:index + 1])
            del pending[:index + 1]
            _remaining(window)
            require(len(line) <= LINE_LIMIT, "RAM_RECEIVER_LINE_LIMIT")
            if first:
                require(line == header, "RAM_RECEIVER_HEADER")
                first = False
            elif line == END:
                require(not pending and len(decoded) == expected_size
                    and hashlib.sha256(decoded).hexdigest() == expected_sha,
                    "RAM_RECEIVER_PACKAGE_PIN")
                return bytes(decoded)
            else:
                require(line.startswith(b"#") and 0 < len(line[1:-1]) <= 1024,
                    "RAM_RECEIVER_DATA_LINE")
                try:
                    part = base64.b64decode(line[1:-1], validate=True)
                except (ValueError, base64.binascii.Error) as error:
                    raise ValueError("RAM_RECEIVER_BASE64") from error
                require(len(decoded) + len(part) <= expected_size, "RAM_RECEIVER_PACKAGE_SIZE")
                decoded.extend(part)
        require(len(pending) < LINE_LIMIT, "RAM_RECEIVER_LINE_LIMIT")


def _execute(raw, window):
    # The receiver's fixed external package digest has already passed. The
    # package main then verifies exact D/tree, all Git tool blobs and C ancestry
    # before importing any of its private modules.
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist()
        require(len(rows) <= 256 and len({r.filename for r in rows}) == len(rows),
            "RAM_RECEIVER_ZIP_MEMBERS")
        item = archive.getinfo("__main__.py")
        require(0 < item.file_size <= 128 * 1024, "RAM_RECEIVER_MAIN_LIMIT")
        source = archive.read(item)
    _remaining(window)
    namespace = {"__name__": "_q2_verified_ram_package"}
    exec(compile(source, "<sha256-pinned-local-preflight-package>", "exec"), namespace)
    result = namespace["run_package"](raw, "--local-preflight", reception_window=dict(window))
    _remaining(window)
    require(type(result) is dict, "RAM_RECEIVER_RESULT")
    return result


def _interrupted(signum, _frame):
    raise ValueError("RAM_RECEIVER_INTERRUPTED_" + str(signum))


def _write_result(raw, window):
    """Finite reporting inside the original 300s; no delayed field work."""
    before = fcntl.fcntl(1, fcntl.F_GETFL)
    try:
        fcntl.fcntl(1, fcntl.F_SETFL, before | os.O_NONBLOCK)
        offset = 0
        while offset < len(raw):
            left = min(window["deadline_ns"] - time.monotonic_ns(),
                window["boottime_deadline_ns"] - time.clock_gettime_ns(time.CLOCK_BOOTTIME))
            require(left > 0, "RAM_RECEIVER_OUTPUT_EXPIRED")
            _, writable, _ = select.select([], [1], [], min(left / 10**9, 1))
            if not writable:
                continue
            try:
                count = os.write(1, raw[offset:offset + 1024])
            except BlockingIOError:
                continue
            require(count > 0, "RAM_RECEIVER_OUTPUT_CLOSED")
            offset += count
    finally:
        fcntl.fcntl(1, fcntl.F_SETFL, before)


def main():
    terminal_before = None
    handlers = {}
    result = None
    # Pure argument validation precedes all terminal and host observations.
    require(len(sys.argv) == 3 and re.fullmatch(r"[0-9a-f]{64}", sys.argv[1]),
        "RAM_RECEIVER_ARGUMENTS")
    expected_sha, expected_size = sys.argv[1], int(sys.argv[2])
    require(0 < expected_size <= 11 * 1024**2, "RAM_RECEIVER_PACKAGE_BOUND")
    window = _window()
    fd = 0
    try:
        # No shell/REPL history is used for payload input. Existing terminal or
        # operating-system auditing is not claimed to be disabled by this tool.
        require(os.isatty(fd) and os.isatty(1), "RAM_RECEIVER_EXISTING_TERMINAL_REQUIRED")
        terminal_before = termios.tcgetattr(fd)
        terminal_input = list(terminal_before)
        terminal_input[3] &= ~(termios.ECHO | termios.ECHONL)
        require(terminal_input[3] & termios.ICANON, "RAM_RECEIVER_CANONICAL_TERMINAL_REQUIRED")
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGALRM):
            handlers[signum] = signal.signal(signum, _interrupted)
        signal.setitimer(signal.ITIMER_REAL, _remaining(window))
        termios.tcsetattr(fd, termios.TCSANOW, terminal_input)
        require(os.write(1, READY) == len(READY), "RAM_RECEIVER_PROMPT_WRITE")
        raw = _frame(fd, expected_size, expected_sha, window)
        result = _execute(raw, window)
    except Exception as error:
        result = dict(schema="q2-local-preflight-ram-receiver/v1", status="LOCAL_PREFLIGHT_BLOCKED",
            reason=type(error).__name__ + ":" + str(error)[:192],
            execution_window_consumed=False, owner_issued=False, remote_called=False, ready=False)
        # Discard only still-pending input on this process's terminal. All
        # supplied payload lines are comments if any remainder reaches shell.
        if terminal_before is not None:
            try:
                termios.tcflush(fd, termios.TCIFLUSH)
            except OSError:
                result["terminal_input_flush"] = "UNKNOWN"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if terminal_before is not None:
            try:
                termios.tcsetattr(fd, termios.TCSANOW, terminal_before)
            except OSError:
                result = dict(schema="q2-local-preflight-ram-receiver/v1", status="LOCAL_PREFLIGHT_BLOCKED",
                    reason="RAM_RECEIVER_TERMINAL_RESTORE_FAILED", observation_result=result,
                    execution_window_consumed=False, owner_issued=False, remote_called=False, ready=False)
        for signum, previous in handlers.items():
            signal.signal(signum, previous)
    # A response is not a durable seal and never upgrades observations to READY.
    raw = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    if len(READY) + len(raw) > OUTPUT_LIMIT - 16384:
        result = dict(schema="q2-local-preflight-ram-receiver/v1", status="LOCAL_PREFLIGHT_BLOCKED",
            reason="RAM_RECEIVER_OUTPUT_LIMIT", execution_window_consumed=False,
            owner_issued=False, remote_called=False, ready=False)
        raw = json.dumps(result, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    _write_result(raw, window)
    return 0 if result.get("status") == "OBSERVED_PARTIAL" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt):
        # A failed output channel cannot safely carry an unbounded traceback
        # or a later replacement report. Absence of complete JSON is incomplete.
        raise SystemExit(2)
