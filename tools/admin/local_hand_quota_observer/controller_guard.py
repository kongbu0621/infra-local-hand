"""Observe an already supervised Q1 controller before any journal construction.

This guard does not create supervision. Its own protected reads, proc/cgroup
reads and manager process creation can block, so the independent outer fixture
must exist before calling it. The fixture also owns the external pipe readers,
finite journal/evidence capacity, fixed controller source/OS installation,
real filesystem UUID and exclusion of other writers. These observations neither
prove Q1/E3 admission nor guarantee termination of blocked kernel I/O. Killing
the controller does not establish that its separately managed query stopped.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import PurePosixPath
import re
import stat
import sys
import time

from .admission import Manifest, Rejected, fields, integer, path, require, token
from .protected_inputs import RuntimeConfig, open_protected, read_fd, verify_file
from .systemd_runtime import Capture, CONTROL_BYTES, _below, _boot_id, _fixed_read, _own_cgroup, boottime_ns


SCHEMA = "local-hand-q1-controller/v1"
SPEC_FIELDS = ("schema", "unit", "invocation_id", "cgroup", "cgroup_device", "cgroup_inode",
               "runtime_max_usec", "timeout_stop_usec", "memory_bytes", "tasks_max",
               "cpu_quota_per_sec_usec", "limit_cpu_seconds")
SHOW_FIELDS = ("Id", "LoadState", "ActiveState", "SubState", "InvocationID", "ControlGroup", "MainPID",
               "ControlPID", "Job", "Slice", "Type", "ExitType", "RemainAfterExit", "Restart",
               "RestartForceExitStatus", "KillMode", "SendSIGKILL", "FinalKillSignal", "NotifyAccess",
               "ExecStartPost", "ExecStop", "ExecStopPost", "ExecReload", "TriggeredBy", "OnFailure",
               "OnSuccess", "RuntimeMaxUSec", "RuntimeRandomizedExtraUSec", "TimeoutStopUSec",
               "TimeoutStopFailureMode", "MemoryMax", "MemorySwapMax", "TasksMax", "CPUQuotaPerSecUSec",
               "LimitCPU", "LimitCPUSoft")
EMPTY_EXEC_FIELDS = ("ExecStartPost", "ExecStop", "ExecStopPost", "ExecReload")


@dataclass(frozen=True)
class ControllerSpec:
    unit: str
    invocation_id: str
    cgroup: str
    cgroup_device: int
    cgroup_inode: int
    runtime_max_usec: int
    timeout_stop_usec: int
    memory_bytes: int
    tasks_max: int
    cpu_quota_per_sec_usec: int
    limit_cpu_seconds: int


@dataclass(frozen=True)
class ControllerObservation:
    unit: str
    invocation_id: str
    cgroup: str
    cgroup_device: int
    cgroup_inode: int
    boot_id: str
    pid: int
    observed_ns: int
    stdout_pipe_device: int
    stdout_pipe_inode: int
    stderr_pipe_device: int
    stderr_pipe_inode: int

    def as_dict(self):
        """Finite identity evidence; this is not a reusable admission token."""
        return asdict(self)


def decode_controller(value):
    """Strict pure configuration decoding; declarations are not host facts."""
    fields(value, SPEC_FIELDS)
    require(value["schema"] == SCHEMA, "CONTROLLER_VERSION")
    unit = token(value["unit"], r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.service")
    cgroup = path(value["cgroup"])
    require(PurePosixPath(cgroup).name == unit and
            PurePosixPath(cgroup).parent.name.endswith(".slice"), "CONTROLLER_CGROUP_LAYOUT")
    return ControllerSpec(unit, token(value["invocation_id"], r"[0-9a-f]{32}"), cgroup,
                          integer(value["cgroup_device"]), integer(value["cgroup_inode"], 1),
                          integer(value["runtime_max_usec"], 1_000_000, 120_000_000),
                          integer(value["timeout_stop_usec"], 1000, 5_000_000),
                          integer(value["memory_bytes"], 16 * 1024**2, 1024**3),
                          integer(value["tasks_max"], 2, 64),
                          integer(value["cpu_quota_per_sec_usec"], 1000, 1_000_000),
                          integer(value["limit_cpu_seconds"], 1, 120))


def _decimal(value):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value) is not None,
            "CONTROLLER_PROPERTY_INTEGER")
    return integer(int(value))


def _timespan_usec(value):
    """Parse the bounded systemctl show format, never guess bare-number units.

    systemd 70bae764 src/shared/bus-print-properties.c formats USec properties
    with FORMAT_TIMESPAN(u, 0). src/basic/time-util.c uses min/s/ms/us and decimal
    fractions for spans below one minute. Only the <=120s subset is needed.
    Unsupported/version-different output is rejected, not silently converted.
    """
    require(type(value) is str and 0 < len(value) <= 64, "CONTROLLER_PROPERTY_TIME")
    if value == "0":
        return 0
    scales = {"min": 60_000_000, "s": 1_000_000, "ms": 1000, "us": 1}
    total, previous = 0, 60_000_001
    for component in value.split(" "):
        match = re.fullmatch(r"(0|[1-9][0-9]{0,8})(?:\.([0-9]{1,6}))?(min|ms|us|s)", component)
        require(match is not None, "CONTROLLER_PROPERTY_TIME")
        whole, fraction, suffix = match.groups()
        scale = scales[suffix]
        require(scale < previous, "CONTROLLER_PROPERTY_TIME")
        previous = scale
        numerator = int(whole) * scale
        if fraction is not None:
            fractional = int(fraction) * scale
            divisor = 10 ** len(fraction)
            require(fractional % divisor == 0, "CONTROLLER_PROPERTY_TIME")
            numerator += fractional // divisor
        total += numerator
        require(total <= 120_000_000, "CONTROLLER_PROPERTY_TIME")
    return total


def _pipe_identity(fd):
    # Linux-only import keeps pure decoding/import collection portable.
    import fcntl

    info = os.fstat(fd)
    require(stat.S_ISFIFO(info.st_mode) and
            os.readlink("/proc/self/fd/" + str(fd)) == "pipe:[" + str(info.st_ino) + "]" and
            fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_WRONLY,
            "CONTROLLER_OUTPUT_PIPE_REQUIRED")
    return info.st_dev, info.st_ino


def _host_identity(config, manifest, spec):
    import resource  # Linux-only runtime read, never a limit-setting operation.

    require(os.getuid() == 0 and os.geteuid() == 0, "CONTROLLER_ADMIN_REQUIRED")
    require(resource.getrlimit(resource.RLIMIT_CPU) == (spec.limit_cpu_seconds, spec.limit_cpu_seconds),
            "CONTROLLER_CPU_LIMIT_CHANGED")
    require(_fixed_read("/proc/1/comm", 128).strip() == b"systemd", "CONTROLLER_SYSTEMD_REQUIRED")
    require(_boot_id() == manifest.boot_id, "CONTROLLER_BOOT_CHANGED")
    expected = (config.initial_userns_device, config.initial_userns_inode)
    for filename in ("/proc/1/ns/user", "/proc/self/ns/user"):
        current = os.stat(filename)
        require((current.st_dev, current.st_ino) == expected, "CONTROLLER_USERNS_CHANGED")
    pid, rows = os.getpid(), {}
    for line in _fixed_read("/proc/self/status", 16384).decode("ascii").splitlines():
        name, separator, value = line.partition(":")
        if separator and name in ("Pid", "Uid"):
            require(name not in rows, "CONTROLLER_PROCESS_IDENTITY")
            rows[name] = value.split()
    require(rows == {"Pid": [str(pid)], "Uid": ["0"] * 4}, "CONTROLLER_PROCESS_IDENTITY")
    require(_own_cgroup() == spec.cgroup, "CONTROLLER_CGROUP_CHANGED")
    require(not _below(spec.cgroup, manifest.cgroup_parent) and
            not _below(manifest.cgroup_parent, spec.cgroup), "CONTROLLER_IN_QUERY_TREE")
    stdout, stderr = _pipe_identity(1), _pipe_identity(2)
    require(stdout != stderr, "CONTROLLER_OUTPUT_PIPE_ALIAS")
    return pid, stdout, stderr


def _cgroup_identity(spec):
    filename = "/sys/fs/cgroup" + spec.cgroup
    fd = open_protected(filename, directory=True)
    try:
        metadata = os.fstat(fd)
        expected = (spec.cgroup_device, spec.cgroup_inode)
        require((metadata.st_dev, metadata.st_ino) == expected, "CONTROLLER_CGROUP_IDENTITY")
        rows = _fixed_read("/proc/self/fdinfo/" + str(fd), 4096).decode("ascii").splitlines()
        mount_ids = [line.split(":", 1)[1].strip() for line in rows if line.startswith("mnt_id:")]
        require(len(mount_ids) == 1 and mount_ids[0].isdigit(), "CONTROLLER_CGROUP_MOUNT")
        matches = []
        for line in _fixed_read("/proc/self/mountinfo", 1024 * 1024).decode("ascii").splitlines():
            row = line.split()
            if row and row[0] == mount_ids[0]:
                require("-" in row and len(row) > row.index("-") + 1, "CONTROLLER_CGROUP_MOUNT")
                matches.append((row[2], row[3], row[4], row[row.index("-") + 1]))
        require(matches == [(str(os.major(metadata.st_dev)) + ":" + str(os.minor(metadata.st_dev)),
                             "/", "/sys/fs/cgroup", "cgroup2")], "CONTROLLER_CGROUP_MOUNT")

        def read(name):
            child = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            try:
                require(stat.S_ISREG(os.fstat(child).st_mode), "CONTROLLER_CGROUP_FILE")
                return read_fd(child, 128).decode("ascii").strip()
            finally:
                os.close(child)

        require(_decimal(read("memory.max")) == spec.memory_bytes and read("memory.swap.max") == "0" and
                _decimal(read("pids.max")) == spec.tasks_max, "CONTROLLER_CGROUP_LIMIT")
        cpu = read("cpu.max").split()
        require(len(cpu) == 2, "CONTROLLER_CGROUP_CPU")
        quota, period = (_decimal(item) for item in cpu)
        require(quota > 0 and 1000 <= period <= 1_000_000 and
                quota * 1_000_000 == spec.cpu_quota_per_sec_usec * period, "CONTROLLER_CGROUP_CPU")
        again = open_protected(filename, directory=True)
        try:
            now = os.fstat(again)
            require((now.st_dev, now.st_ino) == expected, "CONTROLLER_CGROUP_IDENTITY")
        finally:
            os.close(again)
    finally:
        os.close(fd)


def _show_once(config, spec):
    """One manager process with one shared output budget; no fallback/retry."""
    executable = verify_file(config.systemctl_path, config.systemctl_sha256, executable=True)
    capture = Capture(CONTROL_BYTES)
    closed = False
    try:
        end = boottime_ns() + 2_000_000_000
        capture.start((config.systemctl_path, "--system", "--no-pager", "--no-ask-password", "show",
                       spec.unit, "--all", "--property=" + ",".join(SHOW_FIELDS)))
        while boottime_ns() < end:
            capture.pump()
            if capture.done:
                require(capture.process.returncode == 0 and not capture.stderr, "CONTROLLER_MANAGER_FAILED")
                raw = bytes(capture.stdout)
                break
            require(capture.error is None, "CONTROLLER_MANAGER_CAPTURE")
            time.sleep(0.01)
        else:
            raise Rejected("CONTROLLER_MANAGER_TIMEOUT")
        pairs = [line.split("=", 1) for line in raw.decode("ascii").splitlines()]
        require(all(len(pair) == 2 for pair in pairs) and
                len({pair[0] for pair in pairs}) == len(pairs), "CONTROLLER_MANAGER_FORMAT")
        values = dict(pairs)
        # systemd 70bae764 systemctl-show.c print_property() prints one line per
        # Exec command, and zero lines for its empty array even with --all.
        # Normalize ONLY these established Service command-array properties;
        # missing scalar/identity/limit properties remain rejection.
        for name in EMPTY_EXEC_FIELDS:
            values.setdefault(name, "")
        fields(values, SHOW_FIELDS)
        closed = True
        capture.close_pipes()
        require(capture.error is None, "CONTROLLER_MANAGER_CAPTURE")
        return values
    finally:
        # TERM/KILL or client EOF does not prove the controller/query stopped.
        # Preserve the substantive rejection if best-effort client cleanup fails.
        try:
            if not capture.settled:
                capture.kill_client()
                capture.pump()
        except (OSError, ValueError):
            pass
        if not closed:
            try:
                capture.close_pipes()
            except (OSError, ValueError):
                pass
        failing = sys.exc_info()[0] is not None
        try:
            os.close(executable)
        except OSError:
            if not failing:
                raise


def _check_manager(values, spec, pid):
    expected = {"Id": spec.unit, "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
                "InvocationID": spec.invocation_id, "ControlGroup": spec.cgroup, "MainPID": str(pid),
                "ControlPID": "0", "Slice": PurePosixPath(spec.cgroup).parent.name, "Type": "exec",
                "ExitType": "cgroup", "RemainAfterExit": "no", "Restart": "no", "RestartForceExitStatus": "",
                "KillMode": "control-group", "SendSIGKILL": "yes", "FinalKillSignal": "9", "NotifyAccess": "none",
                "ExecStartPost": "", "ExecStop": "", "ExecStopPost": "", "ExecReload": "", "TriggeredBy": "",
                "OnFailure": "", "OnSuccess": "", "TimeoutStopFailureMode": "kill", "MemorySwapMax": "0"}
    require(all(values[name] == value for name, value in expected.items()) and values["Job"] in ("", "0"),
            "CONTROLLER_UNIT_CHANGED")
    require(_timespan_usec(values["RuntimeMaxUSec"]) == spec.runtime_max_usec and
            _timespan_usec(values["RuntimeRandomizedExtraUSec"]) == 0 and
            _timespan_usec(values["TimeoutStopUSec"]) == spec.timeout_stop_usec and
            _timespan_usec(values["CPUQuotaPerSecUSec"]) == spec.cpu_quota_per_sec_usec and
            _decimal(values["MemoryMax"]) == spec.memory_bytes and
            _decimal(values["TasksMax"]) == spec.tasks_max and
            _decimal(values["LimitCPU"]) == spec.limit_cpu_seconds and
            _decimal(values["LimitCPUSoft"]) == spec.limit_cpu_seconds, "CONTROLLER_LIMIT_CHANGED")


def admit_controller(config, manifest, spec):
    """Read the current host; call this before constructing or touching a journal.

    A pure spec or serialized observation cannot replace this call. Failure
    performs no query, journal or quota operation and submits no replacement
    manager command. External supervision remains required on every failure.
    """
    require(type(config) is RuntimeConfig and type(manifest) is Manifest and type(spec) is ControllerSpec,
            "CONTROLLER_INPUT")
    require(sys.platform.startswith("linux"), "CONTROLLER_LINUX_REQUIRED")
    # Recheck strict bounds even when a caller directly constructed the dataclass.
    decode_controller({"schema": SCHEMA, **asdict(spec)})
    try:
        before = _host_identity(config, manifest, spec)
        _cgroup_identity(spec)
        values = _show_once(config, spec)
        _check_manager(values, spec, before[0])
        _cgroup_identity(spec)
        require(_host_identity(config, manifest, spec) == before, "CONTROLLER_IDENTITY_CHANGED")
        pid, stdout, stderr = before
        return ControllerObservation(spec.unit, spec.invocation_id, spec.cgroup, spec.cgroup_device,
                                     spec.cgroup_inode, manifest.boot_id, pid, boottime_ns(), *stdout, *stderr)
    except Rejected:
        raise
    except (OSError, ValueError, UnicodeError) as error:
        raise Rejected("CONTROLLER_IO_UNCERTAIN") from error
