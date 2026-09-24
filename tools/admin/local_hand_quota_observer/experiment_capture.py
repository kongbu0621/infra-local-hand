"""Private Q1 diagnostic collection for an ALREADY started, supervised client.

The trusted fixture supplies original identities and a fixed BOOTTIME deadline,
owns independent collector supervision and finite evidence storage, and must
independently observe/stop the original units. This module starts, signals and
retries nothing, parses no diagnostic JSON, and makes no admission decision.
Only unread, exclusively owned binary Popen pipes (bufsize=0) are accepted;
their read ends are transferred here and closed even after incomplete capture.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import os
import selectors
import stat
import subprocess
import sys

from .admission import Rejected, integer, require, token
from .controller_guard import ControllerObservation
from .supervision import Binding
from .systemd_runtime import boottime_ns


MAX_CAPTURE_BYTES = 128 * 1024  # stdout AND stderr; stderr consumes this budget.
MAX_STDERR_BYTES = 16 * 1024


@dataclass(frozen=True)
class CaptureResult:
    stdout: bytes
    stderr: bytes
    stdout_eof: bool
    stderr_eof: bool
    client_pid: int
    client_returncode: int | None
    error: str | None
    close_errors: tuple[str, ...]
    stdout_closed: bool
    stderr_closed: bool
    stdout_pipe_identity: tuple[int, int] | None
    stderr_pipe_identity: tuple[int, int] | None
    operation: str
    collection_started_ns: int
    collection_deadline_ns: int
    original_binding: Binding
    original_controller: ControllerObservation | None
    original_query_invocation_id: str | None

    @property
    def capture_complete(self):
        """Byte collection only; neither command success nor unit termination."""
        return (self.error is None and not self.close_errors and self.stdout_eof and
                self.stderr_eof and self.client_returncode is not None)

    @property
    def independent_stop_required(self):
        # Even zero exit + both EOF cannot establish either unit's termination.
        # Unknown query invocation must stay unknown; never stop by name alone.
        return True


def _reader_identity(stream):
    import fcntl  # Portable module import; only the live Linux path uses this.

    fd = stream.fileno()
    info = os.fstat(fd)
    require(stat.S_ISFIFO(info.st_mode) and
            os.readlink("/proc/self/fd/" + str(fd)) == "pipe:[" + str(info.st_ino) + "]" and
            fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY,
            "CAPTURE_ANONYMOUS_READER_REQUIRED")
    return info.st_dev, info.st_ino


def capture_existing(process, binding, *, operation, collection_started_ns,
                     collection_deadline_ns, controller=None, original_query_invocation_id=None):
    """Consume the original two pipes once; hand identities back for outer stop.

    Both operations use a separately fixed management window of at most 120
    seconds without renewing the original ticket or reissuing any query. The
    window may cover cleanup diagnostics after the original query deadline;
    complete diagnostic collection never establishes timely query success.
    Both endpoints come from existing outer supervision, never refreshed here. If supplied
    independently, controller observation/pipe correspondence is checked; no
    observation is required to preserve early rejection or bootstrap output.
    Trusted identity provenance and independent supervision remain external.
    Errors after ownership transfer retain partial bytes; closing a read end
    does not invent EOF, a client exit, or independent unit-stop evidence.
    """
    require(sys.platform.startswith("linux"), "CAPTURE_PLATFORM_UNSUPPORTED")
    require(type(process) is subprocess.Popen and type(binding) is Binding and
            (controller is None or type(controller) is ControllerObservation),
            "CAPTURE_ORIGINAL_IDENTITY_REQUIRED")
    require(operation in ("run", "recover_original"), "CAPTURE_OPERATION")
    require(all(type(stream) is io.FileIO and not stream.closed
                for stream in (process.stdout, process.stderr)), "CAPTURE_UNBUFFERED_PIPES_REQUIRED")
    integer(collection_started_ns)
    integer(collection_deadline_ns, collection_started_ns + 1)
    require(collection_deadline_ns <= collection_started_ns + 120_000_000_000,
            "CAPTURE_SUPERVISION_DEADLINE")
    if controller is not None:
        require(controller.boot_id == binding.manifest.boot_id, "CAPTURE_BOOT_CHANGED")
    if original_query_invocation_id is not None:
        token(original_query_invocation_id, r"[0-9a-f]{32}")

    streams = {"stdout": process.stdout, "stderr": process.stderr}
    prefixes = {"stdout": bytearray(), "stderr": bytearray()}
    eof, close_errors = set(), []
    error = returncode = None
    selector = None
    identities = {}
    previous_ns = collection_started_ns
    try:
        identities = {name: _reader_identity(stream) for name, stream in streams.items()}
        require(identities["stdout"] != identities["stderr"], "CAPTURE_PIPE_ALIAS")
        if controller is not None:
            for name, identity in identities.items():
                require(identity == (getattr(controller, name + "_pipe_device"),
                                     getattr(controller, name + "_pipe_inode")), "CAPTURE_PIPE_CHANGED")
        selector = selectors.DefaultSelector()
        for name, stream in streams.items():
            os.set_blocking(stream.fileno(), False)
            selector.register(stream.fileno(), selectors.EVENT_READ, name)
        while True:
            now = boottime_ns()
            integer(now, previous_ns)
            previous_ns = now
            if now >= collection_deadline_ns:
                error = "CAPTURE_DEADLINE_EXPIRED"
                break
            returncode = process.poll()
            if len(eof) == 2 and returncode is not None:
                break
            events = selector.select(min(0.025, (collection_deadline_ns - now) / 1e9))
            for key, _ in events:
                # Recheck after waiting, even when a readable FD wakes us late.
                now = boottime_ns()
                integer(now, previous_ns)
                previous_ns = now
                if now >= collection_deadline_ns:
                    error = "CAPTURE_DEADLINE_EXPIRED"
                    break
                name = key.data
                try:
                    chunk = os.read(key.fd, 4096)
                except BlockingIOError:
                    continue
                if not chunk:
                    eof.add(name)
                    selector.unregister(key.fd)
                    continue
                room = MAX_CAPTURE_BYTES - sum(map(len, prefixes.values()))
                if name == "stderr":
                    room = min(room, MAX_STDERR_BYTES - len(prefixes[name]))
                prefixes[name].extend(chunk[:room])
                if len(chunk) > room:
                    error = "CAPTURE_BYTE_LIMIT"
                    break
            if error is not None:
                break
    except Rejected as failure:
        error = str(failure)
    except KeyboardInterrupt:
        error = "CAPTURE_INTERRUPTED"
    except OSError:
        error = "CAPTURE_IO_UNCERTAIN"
    except Exception:
        error = "CAPTURE_INTERNAL_ERROR"
    finally:
        if selector is not None:
            try:
                selector.close()
            except (Exception, KeyboardInterrupt):
                close_errors.append("SELECTOR_CLOSE_UNCERTAIN")
        for name, stream in streams.items():
            try:
                stream.close()
            except (Exception, KeyboardInterrupt):
                close_errors.append(name.upper() + "_CLOSE_UNCERTAIN")
    return CaptureResult(bytes(prefixes["stdout"]), bytes(prefixes["stderr"]),
                         "stdout" in eof, "stderr" in eof, process.pid, returncode, error,
                         tuple(close_errors), process.stdout.closed, process.stderr.closed,
                         identities.get("stdout"), identities.get("stderr"),
                         operation, collection_started_ns, collection_deadline_ns, binding, controller,
                         original_query_invocation_id)
