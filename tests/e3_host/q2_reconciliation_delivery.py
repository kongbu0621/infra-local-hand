"""Memory-only, bounded transport for the exact reconciliation amendment.

This primitive cannot choose a remote host or renew a delivery window. Callers
provide fixed, independently checked argv. No capture file is opened before
joint live admission; both pipes and stdin share the original dual-clock bound.
Killing an SSH client never proves that its remote process has stopped.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time

NS = 10**9
OUTPUT_LIMIT = 2 * 1024**2
INPUT_LIMIT = 16 * 1024**2
SCHEMA = "local-hand-q2-reconciliation-memory-capture/v1"


def helper(name):
    spec = importlib.util.spec_from_file_location("_reconciliation_delivery_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = helper("q2_startup_retry_delivery")
require, encoded = legacy.require, legacy.encoded


def reason(error):
    text = str(error) if isinstance(error, ValueError) else type(error).__name__
    return text if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", text) else type(error).__name__


def guest_envelope(anchor, *, attempt_id, guest_boot_id, guest_now_ns):
    """Charge the probe and all earlier host work to guest/preparation limits.

    The conservative translated origin is no later than the host origin in
    guest BOOTTIME. The retained schema permits stricter deadlines. No second
    clock probe or wall-clock assumption is used.
    """
    value = legacy.guest_envelope(anchor, attempt_id=attempt_id,
        guest_boot_id=guest_boot_id, guest_now_ns=guest_now_ns)
    origin = (anchor["guest_sample_ns"] -
        (anchor["host_probe_receive_ns"] - anchor["host_issued_ns"]) - anchor["sampling_margin_ns"])
    legacy.number(origin, 1, guest_now_ns)
    value["deadline_ns"] = min(value["deadline_ns"], origin + legacy.GUEST_NS)
    value["preparation_deadline_ns"] = min(value["preparation_deadline_ns"],
        origin + legacy.PREPARATION_NS,
        value["deadline_ns"] - legacy.OWNER_NS - legacy.STOP_NS - legacy.FINALIZATION_NS)
    require(guest_now_ns < value["preparation_deadline_ns"], "RECONCILIATION_PREPARATION_EXPIRED")
    return value


def validate_envelope(anchor, value, *, attempt_id, boot_id, now_ns, preparation=False):
    require(guest_envelope(anchor, attempt_id=attempt_id, guest_boot_id=boot_id,
        guest_now_ns=value["issued_ns"]) == value, "RECONCILIATION_ENVELOPE_CHANGED")
    legacy.number(now_ns, value["issued_ns"])
    end = value["preparation_deadline_ns"] if preparation else value["guest_outer_deadline_ns"] - 2 * NS
    require(now_ns < end, "RECONCILIATION_ORIGINAL_WINDOW_EXPIRED")
    return end


class Window:
    """One origin, established before any host/guest现场 observation."""
    def __init__(self, *, monotonic=time.monotonic_ns, boottime=None):
        self.monotonic = monotonic
        self.boottime = boottime or (lambda: time.clock_gettime_ns(time.CLOCK_BOOTTIME))
        self.boottime_issued_ns = self.boottime()
        self.issued_ns = self.monotonic()
        self.deadline_ns = self.issued_ns + legacy.HOST_NS
        self.boottime_deadline_ns = self.boottime_issued_ns + legacy.HOST_NS
        self.guard()

    def guard(self, reserve_ns=0):
        legacy.number(reserve_ns, 0, legacy.HOST_NS)
        mono, boot = self.monotonic(), self.boottime()
        legacy.validate_host_clock(issued_ns=self.issued_ns, deadline_ns=self.deadline_ns,
            boottime_issued_ns=self.boottime_issued_ns, monotonic_now_ns=mono, boottime_now_ns=boot)
        require(mono + reserve_ns < self.deadline_ns and boot + reserve_ns < self.boottime_deadline_ns,
            "RECONCILIATION_HOST_DEADLINE")
        return mono

    def remaining_ns(self, until_ns):
        return min(until_ns - self.monotonic(),
            self.boottime_issued_ns + until_ns - self.issued_ns - self.boottime())

    def fields(self):
        return dict(issued_ns=self.issued_ns, deadline_ns=self.deadline_ns,
            boottime_issued_ns=self.boottime_issued_ns,
            boottime_deadline_ns=self.boottime_deadline_ns)


def capture_memory(argv, input_bytes, *, window, until_ns, prior_bytes=0,
                   output_limit=None, on_stdout_line=None):
    """Capture one fixed command without touching persistent files.

    ``on_stdout_line`` receives complete bounded bytes. A callback failure is a
    failed transport, never an invitation to run another command or fresh clock.
    Nonzero exit can retain exact EOF evidence but is never CAPTURED success.
    """
    window.guard()
    legacy.number(until_ns, window.issued_ns + 1, window.deadline_ns)
    legacy.number(prior_bytes, 0, OUTPUT_LIMIT)
    available = OUTPUT_LIMIT - prior_bytes
    limit = available if output_limit is None else output_limit
    legacy.number(limit, 1, available)
    require(type(input_bytes) is bytes and len(input_bytes) <= INPUT_LIMIT,
        "RECONCILIATION_TRANSPORT_INPUT_LIMIT")
    require(type(argv) in (list, tuple) and 0 < len(argv) <= 64 and
        all(type(arg) is str and 0 < len(arg) <= 65536 and "\0" not in arg for arg in argv),
        "RECONCILIATION_TRANSPORT_COMMAND")
    require(on_stdout_line is None or callable(on_stdout_line), "RECONCILIATION_LINE_OBSERVER")
    captured = {"stdout": bytearray(), "stderr": bytearray()}
    line = bytearray()
    proc = None
    selector = selectors.DefaultSelector()
    eof = set()
    sent = 0
    error = None
    started = None
    exit_observed = False
    pipe_identities = {}
    stop_reserve = min(NS, max(1, window.remaining_ns(until_ns) // 5))
    try:
        require(window.remaining_ns(until_ns) > stop_reserve, "RECONCILIATION_CAPTURE_TIME")
        proc = subprocess.Popen(list(argv), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True, start_new_session=True)
        started = window.monotonic()
        for name in ("stdout", "stderr"):
            stream = getattr(proc, name)
            os.set_blocking(stream.fileno(), False)
            st = os.fstat(stream.fileno())
            pipe_identities[name] = [st.st_dev, st.st_ino]
            selector.register(stream, selectors.EVENT_READ, name)
        if input_bytes:
            os.set_blocking(proc.stdin.fileno(), False)
            selector.register(proc.stdin, selectors.EVENT_WRITE, "stdin")
        else:
            proc.stdin.close()
        while eof != {"stdout", "stderr"} or proc.poll() is None:
            window.guard()
            remain = window.remaining_ns(until_ns)
            require(remain > stop_reserve, "RECONCILIATION_CAPTURE_TIMEOUT")
            for key, _ in selector.select(min(0.05, remain / NS)):
                if key.data == "stdin":
                    count = os.write(key.fd, input_bytes[sent:sent + 65536])
                    require(count > 0, "RECONCILIATION_STDIN_SHORT_WRITE")
                    sent += count
                    if sent == len(input_bytes):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    continue
                block = os.read(key.fd, 65536)
                if not block:
                    eof.add(key.data)
                    selector.unregister(key.fileobj)
                    continue
                used = sum(len(value) for value in captured.values())
                room = max(0, limit - used)
                kept = block[:room]
                captured[key.data].extend(kept)
                require(len(block) <= room, "RECONCILIATION_CAPTURE_LIMIT")
                if key.data == "stdout" and on_stdout_line is not None:
                    line.extend(kept)
                    while b"\n" in line:
                        end = line.index(b"\n") + 1
                        raw_line = bytes(line[:end])
                        del line[:end]
                        window.guard()
                        on_stdout_line(raw_line)
            if proc.poll() is not None:
                exit_observed = True
        require(sent == len(input_bytes), "RECONCILIATION_STDIN_INCOMPLETE")
        if line and on_stdout_line is not None:
            window.guard()
            on_stdout_line(bytes(line))
    except BaseException as failure:
        error = reason(failure)
    finally:
        if proc is not None:
            if error or proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError:
                    error = error or "RECONCILIATION_CLIENT_KILL_UNPROVEN"
            try:
                # Bounded containment after expiry is still marked expired.
                proc.wait(timeout=max(0.1, min(1.0, max(0, window.remaining_ns(until_ns)) / NS)))
                exit_observed = True
            except subprocess.TimeoutExpired:
                error = error or "RECONCILIATION_CLIENT_EXIT_UNPROVEN"
            for name in ("stdin", "stdout", "stderr"):
                stream = getattr(proc, name)
                if stream is not None and not stream.closed:
                    stream.close()
        selector.close()
    finished = window.monotonic()
    finished_boot = window.boottime()
    within = (finished <= until_ns and
        finished_boot <= window.boottime_issued_ns + until_ns - window.issued_ns)
    raw = {name: bytes(value) for name, value in captured.items()}
    count = sum(map(len, raw.values()))
    complete = (proc is not None and exit_observed and proc.returncode == 0 and
        eof == {"stdout", "stderr"} and error is None and within)
    record = dict(schema=SCHEMA, status="CAPTURED" if complete else "INCOMPLETE",
        complete=complete, started_ns=started, finished_ns=finished,
        finished_boottime_ns=finished_boot, capture_deadline_ns=until_ns,
        **window.fields(), error=error, returncode=proc.returncode if proc else None,
        eof=sorted(eof), original_client_exit_observed=exit_observed,
        pipe_identities=pipe_identities, captured_bytes=count,
        total_captured_bytes=prior_bytes + count, input_bytes=len(input_bytes),
        input_bytes_sent=sent, input_sha256=hashlib.sha256(input_bytes).hexdigest(),
        stdout_sha256=hashlib.sha256(raw["stdout"]).hexdigest(),
        stderr_sha256=hashlib.sha256(raw["stderr"]).hexdigest(),
        within_original_deadline=within, remote_stop_proven=False, q2_accepted=False)
    return dict(record=record, **raw)
