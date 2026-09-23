"""Internal Q1 system-manager assembly. Not installed and not a job entry point.

Run the controller itself in a separately supervised administrative fixture.
Protected installation reads, journal fsync and process creation can block: this
is NOT a listener and does not claim the future Q2 control-response guarantee.
Only the query worker opens target roots. All system-manager commands are fixed.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import PurePosixPath
import re
import stat
import subprocess
import time

from .admission import Rejected, decode_manifest, fields, integer, path, require, strict_json, token
from .protected_inputs import (RuntimeConfig, decode_ticket, encode_ticket, installation_digest,
                               load_runtime, open_protected, read_fd, read_protected, verify_installation)
from .supervision import Binding, Decision, QueryMonitor, UnitObservation


CONTROL_BYTES = 16384
MAX_CONTROL_CALLS = 32
SHOW_FIELDS = ("Id", "LoadState", "ActiveState", "SubState", "InvocationID", "ControlGroup", "Job",
               "ExecMainCode", "ExecMainStatus", "Result", "Slice", "Type", "ExitType", "RemainAfterExit",
               "Restart", "KillMode", "ExecStop", "ExecStopPost", "ExecReload", "TriggeredBy")
ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "SYSTEMD_COLORS": "0"}


def boottime_ns():
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME)


def _fixed_read(filename, maximum=65536):
    fd = os.open(filename, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        return read_fd(fd, maximum)
    finally:
        os.close(fd)


def _boot_id():
    return _fixed_read("/proc/sys/kernel/random/boot_id", 128).decode("ascii").strip()


def _own_cgroup():
    lines = _fixed_read("/proc/self/cgroup", 4096).decode("ascii").splitlines()
    require(len(lines) == 1 and lines[0].startswith("0::/"), "CGROUP_V2_REQUIRED")
    value = lines[0][3:]
    return value if value == "/" else path(value)


def _below(left, right):
    return left == right or PurePosixPath(right) in PurePosixPath(left).parents


def _check_geometry(config, binding, config_path, control_dir):
    path(config_path)
    path(control_dir)
    require(binding.manifest.cgroup_parent == "/" + config.query_slice, "DEDICATED_SLICE_REQUIRED")
    require(binding.manifest.query_uid == 0 and binding.manifest.query_euid == 0, "ADMIN_QUERY_UID_REQUIRED")
    inputs = (config_path, config.manifest_path, config.python_path, config.worker_path, config.native_path,
              config.systemd_run_path, config.systemctl_path,
              *(str(PurePosixPath(config.worker_path).parent / name) for name, _ in config.package_files))
    for item in inputs:
        require(not _below(item, control_dir) and not _below(control_dir, item), "CONTROL_INPUT_OVERLAP")
        require(not _below(item, binding.slot.path) and not _below(binding.slot.path, item), "ROOT_INPUT_OVERLAP")
    require(not _below(binding.slot.path, control_dir) and not _below(control_dir, binding.slot.path),
            "ROOT_CONTROL_OVERLAP")


def unit_command(config, binding, config_path, control_dir, *, now_ns):
    """Exact argv for one already-durable intent. No arbitrary properties/command."""
    require(type(config) is RuntimeConfig and type(binding) is Binding, "RUNTIME_BINDING")
    _check_geometry(config, binding, config_path, control_dir)
    remaining = binding.deadline_ns - integer(now_ns, binding.issued_ns)
    require(remaining >= 1000, "DEADLINE_EXPIRED")
    properties = {
        "Slice": config.query_slice, "Type": "exec", "ExitType": "cgroup", "RemainAfterExit": "yes",
        "Restart": "no", "KillMode": "control-group", "SendSIGKILL": "yes",
        "RuntimeMaxSec": str(remaining // 1000) + "us", "TimeoutStartSec": str(remaining // 1000) + "us",
        "TimeoutStopSec": "1s", "MemoryMax": str(config.memory_bytes), "TasksMax": str(config.tasks_max),
        "CPUQuota": "100%", "LimitCPU": str(config.cpu_seconds), "LimitCORE": "0", "LimitFSIZE": "0",
        "User": "0", "Group": "0", "NoNewPrivileges": "yes", "PrivateUsers": "no",
        "CapabilityBoundingSet": "CAP_SYS_ADMIN CAP_DAC_READ_SEARCH", "AmbientCapabilities": "",
        "PrivateDevices": "yes", "PrivateNetwork": "yes", "PrivateMounts": "yes", "PrivateTmp": "yes",
        "ProtectSystem": "strict", "ProtectControlGroups": "yes", "ProtectKernelTunables": "yes",
        "ProtectKernelModules": "yes", "ProtectKernelLogs": "yes", "RestrictNamespaces": "yes",
        "RestrictSUIDSGID": "yes", "LockPersonality": "yes", "UMask": "0077",
        # quotactl_fd(Q_GETQUOTA) takes mnt_want_write. Keep the exact dedicated
        # mount writable; FD3 itself remains read-only. Native BPF later limits
        # write to its anonymous stdout pipe, not filesystem data.
        "ReadWritePaths": binding.slot.path, "InaccessiblePaths": control_dir,
        "SystemCallFilter": "~@mount @reboot @swap @module @raw-io @debug",
    }
    return (config.systemd_run_path, "--system", "--quiet", "--pipe", "--unit=" + binding.unit,
            "--no-ask-password",
            *("--property=" + key + "=" + value for key, value in properties.items()),
            "--", config.python_path, "-I", "-B", config.worker_path,
            config_path, config.digest, encode_ticket(binding))


class Capture:
    """Finite anonymous-pipe capture for a known manager command, no target I/O."""
    def __init__(self, limit):
        self.limit = integer(limit, 1, 32768)
        self.process = None
        self.stdout = bytearray()
        self.stderr = bytearray()
        self.eof = set()
        self.error = None
        self.configured = False

    def start(self, argv):
        require(self.process is None, "CAPTURE_ALREADY_STARTED")
        self.process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, close_fds=True, env=ENVIRONMENT)
        for stream in (self.process.stdout, self.process.stderr):
            os.set_blocking(stream.fileno(), False)
        self.configured = True

    def pump(self):
        if self.process is None or not self.configured:
            self.error = self.error or "CAPTURE_SETUP_UNCERTAIN"
            return
        for name in ("stdout", "stderr"):
            if name in self.eof:
                continue
            stream = getattr(self.process, name)
            try:
                chunk = os.read(stream.fileno(), min(4096, self.limit + 1))
            except BlockingIOError:
                continue
            except OSError:
                self.error = self.error or "CAPTURE_IO_UNCERTAIN"
                continue
            if not chunk:
                self.eof.add(name)
                continue
            room = self.limit - len(self.stdout) - len(self.stderr)
            getattr(self, name).extend(chunk[:room])
            if len(chunk) > room:
                self.error = self.error or "CAPTURE_BYTE_LIMIT"

    @property
    def exited(self):
        return self.process is not None and self.process.poll() is not None

    @property
    def settled(self):
        return self.exited and len(self.eof) == 2

    @property
    def done(self):
        return self.settled and self.error is None

    def kill_client(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()  # This never proves the query unit exited.

    def close_pipes(self):
        if self.process is not None:
            for stream in (self.process.stdout, self.process.stderr):
                try:
                    stream.close()
                except OSError:
                    self.error = self.error or "CAPTURE_CLOSE_UNCERTAIN"


@dataclass(frozen=True)
class Outcome:
    decision: Decision
    binding: Binding
    stdout: bytes
    stderr: bytes
    invocation_id: str | None
    empty_scope: str
    control_calls: int
    cleanup_reason: str | None = None
    journal_reason: str | None = None
    pending_clients: tuple[int, ...] = ()
    unit_facts: tuple[tuple[str, str], ...] = ()


class Q1Controller:
    """Single-query source assembly for an explicitly prepared admin fixture.

    No socket, automatic startup, installation, root allocation or quota setting.
    The caller owns this independently supervised controller and its journal.
    On UNKNOWN all original reservations remain retained; no cleanup by retry.
    """
    def __init__(self, config_path, config_digest, journal):
        self.config_path = path(config_path)
        self.config = load_runtime(config_path, config_digest)
        self.manifest = decode_manifest(read_protected(self.config.manifest_path, 32768),
                                        self.config.manifest_digest)
        require(installation_digest(self.config) == self.manifest.installation_digest, "INSTALLATION_BINDING")
        self.journal = journal
        self.launcher = None
        self.controls = []
        self._used = False

    def _admit_host(self, binding, *, require_empty=True):
        require(os.getuid() == 0 and os.geteuid() == 0, "ADMIN_CONTROLLER_REQUIRED")
        require(_fixed_read("/proc/1/comm", 128).strip() == b"systemd", "SYSTEMD_HOST_REQUIRED")
        require(_boot_id() == binding.manifest.boot_id, "BOOT_CHANGED")
        current = os.stat("/proc/1/ns/user")
        own = os.stat("/proc/self/ns/user")
        expected = (self.config.initial_userns_device, self.config.initial_userns_inode)
        require((current.st_dev, current.st_ino) == expected == (own.st_dev, own.st_ino), "USERNS_CHANGED")
        require(not _below(_own_cgroup(), binding.manifest.cgroup_parent), "CONTROLLER_IN_QUERY_TREE")
        self.journal.verify_directory()
        _check_geometry(self.config, binding, self.config_path, self.journal.control_dir)
        native_fd = verify_installation(self.config)
        os.close(native_fd)
        empty = self._parent_empty(binding)
        require(not require_empty or empty, "QUERY_TREE_NOT_EMPTY")

    def _parent_empty(self, binding):
        """A bound dedicated parent proves all descendants empty after pruning."""
        filename = "/sys/fs/cgroup" + binding.manifest.cgroup_parent
        parent = open_protected(filename, directory=True)
        try:
            before = os.fstat(parent)
            expected = (self.config.cgroup_parent_device, self.config.cgroup_parent_inode)
            require((before.st_dev, before.st_ino) == expected, "CGROUP_PARENT_CHANGED")
            info = _fixed_read("/proc/self/fdinfo/" + str(parent), 4096).decode("ascii").splitlines()
            ids = [line.split(":", 1)[1].strip() for line in info if line.startswith("mnt_id:")]
            require(len(ids) == 1 and ids[0].isdigit(), "CGROUP_MOUNT_ID")
            mounts = []
            for line in _fixed_read("/proc/self/mountinfo", 1024 * 1024).decode("utf-8").splitlines():
                row = line.split()
                if row and row[0] == ids[0]:
                    separator = row.index("-")
                    mounts.append((row[2], row[separator + 1]))
            require(mounts == [(str(os.major(before.st_dev)) + ":" + str(os.minor(before.st_dev)), "cgroup2")],
                    "CGROUP_FILESYSTEM")
            events = os.open("cgroup.events", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                             dir_fd=parent)
            try:
                require(stat.S_ISREG(os.fstat(events).st_mode), "CGROUP_EVENTS_TYPE")
                rows = [line.split() for line in read_fd(events, 4096).decode("ascii").splitlines()]
                require(all(len(row) == 2 for row in rows) and len({row[0] for row in rows}) == len(rows),
                        "CGROUP_EVENTS_FORMAT")
                values = dict(rows)
                require(values.get("populated") in ("0", "1"), "CGROUP_POPULATED_MISSING")
            finally:
                os.close(events)
            again = open_protected(filename, directory=True)
            try:
                now = os.fstat(again)
                require((now.st_dev, now.st_ino) == expected, "CGROUP_PARENT_CHANGED")
            finally:
                os.close(again)
            return values["populated"] == "0"
        finally:
            os.close(parent)

    def _command(self, arguments, *, absolute_end_ns):
        require(len(self.controls) < MAX_CONTROL_CALLS and all(item.settled for item in self.controls),
                "CONTROL_PROCESS_UNRESOLVED")
        require(boottime_ns() < absolute_end_ns, "CONTROL_DEADLINE_EXPIRED")
        capture = Capture(CONTROL_BYTES)
        self.controls.append(capture)  # Register before process creation can fail.
        capture.start((self.config.systemctl_path, "--system", "--no-pager", "--no-ask-password", *arguments))
        end = min(absolute_end_ns, boottime_ns() + 2_000_000_000)
        while boottime_ns() < end:
            capture.pump()
            if self.launcher is not None:
                self.launcher.pump()
            if capture.done:
                require(capture.process.returncode == 0, "MANAGER_COMMAND_FAILED")
                return bytes(capture.stdout)
            if capture.error:
                break
            time.sleep(0.01)
        capture.kill_client()
        capture.pump()
        raise Rejected("MANAGER_COMMAND_UNCERTAIN")

    def _show(self, binding, *, absolute_end_ns):
        raw = self._command(("show", binding.unit, "--property=" + ",".join(SHOW_FIELDS)),
                            absolute_end_ns=absolute_end_ns)
        pairs = [line.split("=", 1) for line in raw.decode("utf-8", "strict").splitlines()]
        require(all(len(item) == 2 for item in pairs) and len({item[0] for item in pairs}) == len(pairs),
                "UNIT_PROPERTIES_FORMAT")
        return fields(dict(pairs), SHOW_FIELDS)

    def _unit_identity(self, binding, values, *, invocation=None):
        require(values["Id"] == binding.unit and values["LoadState"] == "loaded", "UNIT_NOT_RETAINED")
        actual = token(values["InvocationID"], r"[0-9a-f]{32}")
        require(invocation in (None, actual), "INVOCATION_CHANGED")
        require(values["ControlGroup"] in (binding.cgroup, ""), "UNIT_CGROUP_CHANGED")
        expected = {"Slice": self.config.query_slice, "Type": "exec", "ExitType": "cgroup",
                    "RemainAfterExit": "yes", "Restart": "no", "KillMode": "control-group",
                    "ExecStop": "", "ExecStopPost": "", "ExecReload": "", "TriggeredBy": ""}
        require(all(values[key] == value for key, value in expected.items()), "UNIT_CONFIG_CHANGED")
        return actual

    def _ready(self, binding, raw):
        line, separator, native = raw.partition(b"\n")
        require(separator and len(line) <= 2048, "WORKER_READY_MISSING")
        value = fields(strict_json(line, 2048, depth=2), (
            "schema", "boot_id", "unit", "invocation_id", "cgroup", "manifest_digest", "runtime_digest", "request_id"))
        require(value["schema"] == "local-hand-quota-worker-ready/v1" and
                value["boot_id"] == binding.manifest.boot_id and value["unit"] == binding.unit and
                value["cgroup"] == binding.cgroup and value["manifest_digest"] == binding.manifest.digest and
                value["runtime_digest"] == self.config.digest and value["request_id"] == binding.request_id,
                "WORKER_IDENTITY_CHANGED")
        token(value["invocation_id"], r"[0-9a-f]{32}")
        return value["invocation_id"], native

    def _drain(self, absolute_end_ns):
        """Drain owned pipes only; killed/absent processes are not unit proof."""
        captures = self.controls + ([self.launcher] if self.launcher else [])
        while boottime_ns() < absolute_end_ns:
            pending = [item for item in captures if not item.settled]
            if not pending:
                return
            for item in pending:
                item.pump()
            time.sleep(0.01)

    def _stop_original(self, binding, invocation, *, absolute_end_ns, recovering=False):
        # There is at most one stop submission in this controller instance. A
        # failed manager client is retained; never spawn replacements around it.
        require(not self._stop_attempted, "ORIGINAL_STOP_ALREADY_ATTEMPTED")
        self._stop_attempted = True
        for item in self.controls:
            if not item.settled:
                item.pump()
        require(_boot_id() == binding.manifest.boot_id, "BOOT_CHANGED")
        values = self._show(binding, absolute_end_ns=absolute_end_ns)
        if values["LoadState"] == "loaded":
            self._unit_identity(binding, values, invocation=invocation)
            self._command(("stop", binding.unit), absolute_end_ns=absolute_end_ns)
        else:
            require(values["Id"] == binding.unit and values["LoadState"] == "not-found" and
                    values["Job"] in ("", "0"), "UNIT_NOT_STOPPED")
        self._drain(absolute_end_ns)
        require(all(item.settled for item in self.controls), "CONTROL_PROCESS_UNRESOLVED")
        if not recovering:
            require(self.launcher is not None and self.launcher.settled, "COLLECTOR_EXIT_UNPROVEN")
        require(self._parent_empty(binding), "QUERY_TREE_NOT_EMPTY")
        after = self._show(binding, absolute_end_ns=absolute_end_ns)
        if after["LoadState"] == "loaded":
            self._unit_identity(binding, after, invocation=invocation)
            require(after["ActiveState"] in ("inactive", "failed") and after["Job"] in ("", "0"),
                    "UNIT_NOT_STOPPED")
        else:
            require(after["Id"] == binding.unit and after["LoadState"] == "not-found" and
                    after["Job"] in ("", "0"), "UNIT_NOT_STOPPED")
        require(_boot_id() == binding.manifest.boot_id and self._parent_empty(binding), "STOP_FACTS_CHANGED")
        # A recovered controller does not own or authenticate original pipes or
        # launcher lifetime. Its newly completed clients cannot replace them.
        return not recovering

    def _finish(self, binding, decision, invocation, terminal=None, cleanup_reason=None):
        captures = self.controls + ([self.launcher] if self.launcher else [])
        pending = tuple(item.process.pid for item in captures
                        if item.process is not None and not item.settled)
        for item in captures:
            if item.settled:
                item.close_pipes()
        if decision.status == "OBSERVED" and any(item.error for item in captures):
            decision = Decision("UNKNOWN", "COLLECTOR_IO_UNCERTAIN", query_stopped=decision.query_stopped)
        journal_reason = None
        if decision.status != "OBSERVED":
            try:
                record = self.journal.read(binding)
                if record.status != "UNKNOWN":
                    self.journal.mark_unknown(binding, "Q1_QUERY_UNKNOWN")
            except (Rejected, OSError) as error:
                # Never overwrite the original failure (or an earlier permanent
                # UNKNOWN reason) with secondary bookkeeping failure.
                journal_reason = str(error) if isinstance(error, Rejected) else "JOURNAL_IO_UNCERTAIN"
        return Outcome(decision, binding, bytes(self.launcher.stdout) if self.launcher else b"",
                       bytes(self.launcher.stderr) if self.launcher else b"", invocation,
                       binding.manifest.cgroup_parent, len(self.controls), cleanup_reason,
                       journal_reason, pending, tuple((terminal or {}).items()))

    def run(self, ticket):
        """One explicit Q1 call. Stop and both EOFs must meet its original deadline.

        An extra three seconds permits administrative cleanup only; it never
        makes late facts successful and never extends unit RuntimeMaxSec.
        """
        require(not self._used, "CONTROLLER_ALREADY_USED")
        self._used = True
        self._stop_attempted = False
        binding = decode_ticket(ticket, self.manifest)
        invocation = None
        terminal = None
        stopped = False
        cleanup_reason = None
        end = binding.deadline_ns + 3_000_000_000
        decision = Decision("UNKNOWN", "QUERY_NOT_COMPLETED")
        try:
            try:
                prior = self.journal.read(binding)
            except Rejected as error:
                if str(error) != "INTENT_REQUIRED":
                    raise
            else:
                return self._finish(binding, Decision("UNKNOWN", "ORIGINAL_INTENT_RETAINED"),
                                    prior.invocation_id)
            self._admit_host(binding)

            def deliver(original):
                self.journal.verify_directory()
                require(_boot_id() == original.manifest.boot_id, "BOOT_CHANGED")
                before = self._show(original, absolute_end_ns=original.deadline_ns)
                require(before["Id"] == original.unit and before["LoadState"] == "not-found" and
                        before["Job"] in ("", "0"), "UNIT_ALREADY_EXISTS")
                command = unit_command(self.config, original, self.config_path, self.journal.control_dir,
                                       now_ns=boottime_ns())
                self.launcher = Capture(self.config.max_output_bytes)
                self.launcher.start(command)

            delivery = self.journal.deliver_once(binding, deliver)
            if not delivery.delivered:
                return self._finish(binding, Decision("UNKNOWN", "ORIGINAL_INTENT_RETAINED"),
                                    delivery.record.invocation_id)
            # At most 25 polling shows, leaving seven manager calls for the
            # pre-delivery check and original-identity stop/final checks.
            interval = max(0.01, (binding.deadline_ns - binding.issued_ns) / 24_000_000_000)
            for _ in range(25):
                if boottime_ns() >= binding.deadline_ns:
                    break
                self.launcher.pump()
                require(self.launcher.error is None, "QUERY_CAPTURE_UNCERTAIN")
                values = self._show(binding, absolute_end_ns=binding.deadline_ns)
                require(values["Id"] == binding.unit, "UNIT_ID_CHANGED")
                pending_start = (invocation is None and
                                 (values["LoadState"] == "not-found" or
                                  (values["LoadState"] == "loaded" and values["InvocationID"] == "")))
                if not pending_start:
                    current = self._unit_identity(binding, values, invocation=invocation)
                    if invocation is None:
                        # Keep the observed identity in memory even if fsync
                        # fails; recovery still cannot invent a missing record.
                        invocation = current
                        self.journal.remember_invocation(binding, current)
                    finished = ((values["ActiveState"], values["SubState"]) == ("active", "exited") or
                                values["ActiveState"] in ("inactive", "failed"))
                    if finished and values["Job"] in ("", "0"):
                        terminal = dict(values)
                        require(self._parent_empty(binding), "QUERY_TREE_NOT_EMPTY")
                        break
                require(not self.launcher.exited, "LAUNCHER_EXIT_BEFORE_PROOF")
                time.sleep(min(interval, max(0, binding.deadline_ns - boottime_ns()) / 1e9))
            require(invocation is not None, "ORIGINAL_INVOCATION_REQUIRED")
            stopped = self._stop_original(binding, invocation, absolute_end_ns=end)
            require(terminal is not None, "TIMELY_TERMINAL_FACTS_MISSING")
            require(self.launcher.done and all(item.done for item in self.controls), "COLLECTOR_IO_UNCERTAIN")
            require(terminal["Result"] == "success", "QUERY_UNIT_UNSUCCESSFUL")
            require(self.launcher.process.returncode == 0, "LAUNCHER_UNSUCCESSFUL")
            worker_invocation, raw = self._ready(binding, bytes(self.launcher.stdout))
            require(worker_invocation == invocation, "WORKER_INVOCATION_CHANGED")
            require(terminal["ExecMainCode"].isdigit() and terminal["ExecMainStatus"].isdigit(), "EXEC_STATUS_MISSING")
            monitor = QueryMonitor(binding, original_invocation=invocation)
            now = boottime_ns()
            monitor.feed(raw, now_ns=now)
            monitor.eof(now_ns=now)
            decision = monitor.inspect(UnitObservation(
                binding.manifest.boot_id, binding.unit, invocation, binding.cgroup, now,
                True, True, True, True, True, True, int(terminal["ExecMainCode"]), int(terminal["ExecMainStatus"]),
                empty_cgroup=binding.manifest.cgroup_parent), now_ns=now)
        except (Rejected, OSError, ValueError) as error:
            reason = str(error) if isinstance(error, Rejected) else "RUNTIME_IO_UNCERTAIN"
            if invocation is not None and not self._stop_attempted:
                try:
                    stopped = self._stop_original(binding, invocation, absolute_end_ns=end)
                except (Rejected, OSError, ValueError) as cleanup_error:
                    cleanup_reason = (str(cleanup_error) if isinstance(cleanup_error, Rejected)
                                      else "CLEANUP_IO_UNCERTAIN")
            decision = Decision("UNKNOWN", reason, query_stopped=stopped)
        return self._finish(binding, decision, invocation, terminal, cleanup_reason)

    def recover_original(self, ticket):
        """Observe/stop a journaled original; never launch or restore lost output.

        No original InvocationID means no stop. Missing original launcher/pipe
        ownership means UNKNOWN even after a matching unit and parent are empty.
        Permanent intent/resource reservations are never removed here.
        """
        require(not self._used, "CONTROLLER_ALREADY_USED")
        self._used = True
        self._stop_attempted = False
        binding = decode_ticket(ticket, self.manifest)
        invocation = None
        terminal = None
        cleanup_reason = None
        try:
            record = self.journal.read(binding)
            invocation = record.invocation_id
            self._admit_host(binding, require_empty=False)
            end = boottime_ns() + 3_000_000_000
            terminal = self._show(binding, absolute_end_ns=end)
            require(invocation is not None, "ORIGINAL_INVOCATION_REQUIRED")
            self._unit_identity(binding, terminal, invocation=invocation)
            self._stop_original(binding, invocation, absolute_end_ns=end, recovering=True)
            reason = "ORIGINAL_COLLECTOR_AND_OUTPUT_LOST"
        except (Rejected, OSError, ValueError) as error:
            reason = str(error) if isinstance(error, Rejected) else "RECOVERY_IO_UNCERTAIN"
            cleanup_reason = reason
        return self._finish(binding, Decision("UNKNOWN", reason), invocation, terminal, cleanup_reason)
