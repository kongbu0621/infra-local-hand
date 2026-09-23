"""Bounded, read-only E3 preparation inventory, not an acceptance harness.

Run using Python 3.9+; the product still requires Python 3.12+. Exit zero means
one report was generated. It never authorizes business, services or deployment.
This standalone tool is deliberately outside the four installed runtime packages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import selectors
import signal
import stat
import subprocess
import sys
import time

SCHEMA_VERSION = "infra-local-hand-e3-host-probe/v1"
MAX_REPORT_BYTES = 131072
MAX_FILE_BYTES = 1048576
MAX_COMMAND_BYTES = 65536
COMMAND_TIMEOUT_SECONDS = 2.0
UNVERIFIED_BLOCKERS = ("REAL_HARNESS_MISSING", "QUOTA_PERMISSION_MODEL_UNVERIFIED", "E3_SUPERVISION_UNVERIFIED")
_UNRESOLVED_CHILDREN = []
_CONTROLLERS = frozenset(("cpu", "cpuset", "io", "memory", "pids", "hugetlb", "rdma", "misc", "dmem"))
_REQUIRED_CONTROLLERS = frozenset(("cpu", "memory", "pids"))
_CGROUP_FILES = ("cgroup.controllers", "cgroup.subtree_control", "cgroup.type", "cgroup.events",
                 "cgroup.max.depth", "cgroup.max.descendants", "cpu.max", "memory.max", "pids.max")


class ProbeError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # Never reflect an unrecognized argument, path or credential-shaped text.
        self.exit(2, "Invalid probe arguments; only the documented read-only options are accepted.\n")


def _canonical_path(value):
    if (type(value) is not str or not value.startswith("/") or value.startswith("//")
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or str(PurePosixPath(value)) != value or ".." in PurePosixPath(value).parts):
        raise ValueError("noncanonical absolute path")
    if len(value.encode("utf-8", "strict")) > 4096:
        raise ValueError("path length")
    return value


def parse_args(argv=None):
    parser = _Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("--label", choices=("scratch", "candidate"), default="candidate")
    parser.add_argument("--expected-uid", type=int)
    parser.add_argument("--cgroup")
    parser.add_argument("--slice")
    parser.add_argument("--mount-target", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        if args.expected_uid is not None and not 0 <= args.expected_uid < 2**32 - 1:
            raise ValueError("uid")
        if (args.cgroup is not None) != (args.slice is not None):
            raise ValueError("paired cgroup and slice")
        if args.cgroup is not None:
            _canonical_path(args.cgroup)
            if not (args.cgroup == "/sys/fs/cgroup" or args.cgroup.startswith("/sys/fs/cgroup/")):
                raise ValueError("cgroup namespace")
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,200}\.slice", args.slice) is None:
                raise ValueError("slice")
        if len(args.mount_target) > 8:
            raise ValueError("mount count")
        for target in args.mount_target:
            _canonical_path(target)
    except (ValueError, UnicodeError):
        parser.error("invalid private input")
    return args


def _directory_fd(path):
    """Walk literal local directories with no symlink following, including parents."""
    _canonical_path(path)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open("/", flags)
    try:
        for part in PurePosixPath(path).parts[1:]:
            child = os.open(part, flags, dir_fd=descriptor)
            parent = descriptor
            descriptor = child
            # Transfer ownership before close: a failed close must not leak
            # the new child or retry a descriptor whose state is uncertain.
            os.close(parent)
        return descriptor
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _read_fd(descriptor, maximum):
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        raise ProbeError("NOT_REGULAR")
    chunks, seen = [], 0
    while True:
        chunk = os.read(descriptor, min(65536, maximum + 1 - seen))
        if not chunk:
            return b"".join(chunks)
        seen += len(chunk)
        if seen > maximum:
            raise ProbeError("BYTE_LIMIT")
        chunks.append(chunk)


def read_bounded(path, maximum):
    if type(maximum) is not int or not 0 < maximum <= MAX_FILE_BYTES:
        raise ValueError("invalid fixed read bound")
    path = _canonical_path(os.fspath(path))
    parent = _directory_fd(str(PurePosixPath(path).parent))
    try:
        descriptor = os.open(PurePosixPath(path).name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0), dir_fd=parent)
        try:
            return _read_fd(descriptor, maximum)
        finally:
            os.close(descriptor)
    finally:
        os.close(parent)


def _capture(argv, environment, *, timeout_seconds=COMMAND_TIMEOUT_SECONDS, max_output_bytes=MAX_COMMAND_BYTES):
    """Bound both streams together while running, including failure cleanup.

    Production callers supply only the fixed commands below. This private seam
    also permits harmless local child fixtures in tests; the CLI has no argv or
    environment injection interface. No raw stderr is returned.
    """
    if not 0 < timeout_seconds <= 10 or not 0 < max_output_bytes <= MAX_COMMAND_BYTES:
        raise ValueError("invalid command observation bound")
    result = {"status": "LAUNCH_FAILED", "trigger": None, "cleanup": "CONFIRMED", "exit_code": None,
              "stdout": b"", "stdout_bytes_seen": 0, "stderr_bytes_seen": 0, "output_limit_bytes": max_output_bytes}
    if len(_UNRESOLVED_CHILDREN) >= 4:
        return dict(result, status="UNRESOLVED", cleanup="UNRESOLVED", trigger="PREVIOUS_CHILDREN_UNRESOLVED")
    process = None
    selector = None
    buffers = bytearray()
    total = 0
    cleanup_errors = []
    started = time.monotonic()
    try:
        process = subprocess.Popen(list(argv), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=dict(environment), shell=False, close_fds=True, start_new_session=True)
        selector = selectors.DefaultSelector()
        for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        result["status"] = "COMPLETED"
        while selector.get_map() or process.poll() is None:
            remaining = timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                result["status"] = "TIMEOUT"
                break
            for key, _ in selector.select(min(0.05, remaining)):
                try:
                    chunk = os.read(key.fileobj.fileno(), min(65536, max_output_bytes + 1 - total))
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                result[key.data + "_bytes_seen"] += len(chunk)
                accepted = min(len(chunk), max(0, max_output_bytes - total))
                if key.data == "stdout":
                    buffers.extend(chunk[:accepted])
                total += len(chunk)
                if total > max_output_bytes:
                    result["status"] = "OUTPUT_LIMIT"
                    break
            if result["status"] != "COMPLETED":
                break
    except Exception as error:
        result["status"] = "LAUNCH_FAILED" if process is None else "OBSERVATION_FAILED"
        result["error_type"] = type(error).__name__
        if isinstance(error, OSError):
            result["errno"] = error.errno
    finally:
        result["trigger"] = result["status"]
        if process is not None:
            try:
                alive = process.poll() is None
            except Exception as error:
                alive = True
                cleanup_errors.append(type(error).__name__)
            if alive:
                # Popen's own session is the only signal target. There is no
                # service mutation and no unbounded communicate()/wait().
                for sig, grace in ((signal.SIGTERM, 0.2), (signal.SIGKILL, 0.35)):
                    try:
                        if process.poll() is not None:
                            break
                        os.killpg(process.pid, sig)
                    except ProcessLookupError:
                        pass
                    except Exception as error:
                        cleanup_errors.append(type(error).__name__)
                    until = time.monotonic() + grace
                    while time.monotonic() < until:
                        try:
                            if process.poll() is not None:
                                break
                        except Exception as error:
                            cleanup_errors.append(type(error).__name__)
                            break
                        time.sleep(0.01)
            try:
                result["exit_code"] = process.poll()
            except Exception as error:
                cleanup_errors.append(type(error).__name__)
            if result["exit_code"] is None:
                _UNRESOLVED_CHILDREN.append(process)
                cleanup_errors.append("CHILD_EXIT_UNCONFIRMED")
            else:
                # Even a reaped direct child does not prove all members of its
                # private process group have exited. Signal zero only observes.
                try:
                    os.killpg(process.pid, 0)
                    cleanup_errors.append("PROCESS_GROUP_EXIT_UNCONFIRMED")
                except ProcessLookupError:
                    pass
                except Exception as error:
                    cleanup_errors.append(type(error).__name__)
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except Exception as error:
                        cleanup_errors.append(type(error).__name__)
        if selector is not None:
            try:
                selector.close()
            except Exception as error:
                cleanup_errors.append(type(error).__name__)
        if cleanup_errors:
            result.update(status="UNRESOLVED", cleanup="UNRESOLVED", cleanup_errors=sorted(set(cleanup_errors)))
        result["stdout"] = bytes(buffers)
        result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    return result


def _mount_path(value):
    def decode(match):
        escapes = {"040": " ", "011": "\t", "012": "\n", "134": "\\"}
        if match.group(1) not in escapes:
            raise ProbeError("MOUNTINFO_FORMAT")
        return escapes[match.group(1)]
    value = re.sub(r"\\([0-9]{3})", decode, value)
    return _canonical_path(value)


def _mount_root(value, filesystem):
    # nsfs.show_path emits a namespace handle, not an absolute pathname.
    # Keep it opaque and retain the mount: dropping a namespace overmount
    # could expose the underlying cgroup2 record as a false observation.
    if filesystem == "nsfs":
        match = re.fullmatch(r"[a-z][a-z0-9_]{0,31}:\[([1-9][0-9]{0,19})\]", value)
        if match and int(match.group(1)) <= 2**64 - 1:
            return value
    return _mount_path(value)


def parse_mountinfo(raw):
    if type(raw) is not bytes or len(raw) > MAX_FILE_BYTES:
        raise ProbeError("MOUNTINFO_BYTE_LIMIT")
    records = []
    try:
        for line in raw.decode("utf-8", "strict").splitlines():
            fields = line.split(" ")
            separator = fields.index("-")
            if separator < 6 or len(fields) != separator + 4:
                raise ValueError("mount fields")
            mount_id, parent_id = int(fields[0]), int(fields[1])
            filesystem = fields[separator + 1]
            if (mount_id <= 0 or parent_id < 0 or re.fullmatch(r"[0-9]+:[0-9]+", fields[2]) is None
                    or re.fullmatch(r"[A-Za-z0-9_.+-]{1,64}", filesystem) is None):
                raise ValueError("mount identity")
            options = set(fields[5].split(",")) | set(fields[separator + 3].split(","))
            records.append({"mount_id": mount_id, "parent_id": parent_id, "device": fields[2],
                "root": _mount_root(fields[3], filesystem), "mount_point": _mount_path(fields[4]), "type": filesystem,
                "read_only": "ro" in set(fields[5].split(",")), "prjquota": "prjquota" in options,
                "pquota": "pquota" in options})
        if not records or len({item["mount_id"] for item in records}) != len(records):
            raise ValueError("mount identity missing or duplicated")
    except (ValueError, UnicodeError, IndexError) as error:
        raise ProbeError("MOUNTINFO_FORMAT") from error
    return records


def match_mount(target, mounts):
    """Pure lexical component match: does not prove target existence or access."""
    _canonical_path(target)
    matches = [item for item in mounts if item["mount_point"] == "/" or
               target == item["mount_point"] or target.startswith(item["mount_point"] + "/")]
    if not matches:
        return None
    maximum = max(len(item["mount_point"]) for item in matches)
    best = [item for item in matches if len(item["mount_point"]) == maximum]
    if len(best) != 1:
        raise ProbeError("AMBIGUOUS_OVERMOUNT")
    return dict(best[0])


def _fd_mount_id(descriptor):
    raw = read_bounded("/proc/" + str(os.getpid()) + "/fdinfo/" + str(descriptor), 4096)
    values = [line.split(":", 1)[1].strip() for line in raw.decode("ascii", "strict").splitlines() if line.startswith("mnt_id:")]
    if len(values) != 1 or not values[0].isdigit():
        raise ProbeError("FD_MOUNT_ID_UNAVAILABLE")
    return int(values[0])


def _controller_names(raw):
    words = raw.decode("ascii", "strict").strip().split()
    if len(words) != len(set(words)) or any(word not in _CONTROLLERS for word in words):
        raise ProbeError("CONTROLLER_FORMAT_OR_VERSION")
    return sorted(words)


def _cgroup_value(name, raw):
    if name in ("cgroup.controllers", "cgroup.subtree_control"):
        return _controller_names(raw)
    value = raw.decode("ascii", "strict").strip()
    if name == "cgroup.type":
        if value not in ("domain", "domain threaded", "domain invalid", "threaded"):
            raise ProbeError("CGROUP_FILE_FORMAT_OR_VERSION")
        return value
    if name == "cgroup.events":
        output = {}
        for line in value.splitlines():
            key, number = line.split()
            if key not in ("populated", "frozen") or number not in ("0", "1") or key in output:
                raise ProbeError("CGROUP_FILE_FORMAT_OR_VERSION")
            output[key] = int(number)
        if "populated" not in output:
            raise ProbeError("CGROUP_FILE_FORMAT_OR_VERSION")
        return output
    if name == "cpu.max":
        values = value.split()
        if len(values) != 2 or (values[0] != "max" and not values[0].isdigit()) or not values[1].isdigit():
            raise ProbeError("CGROUP_FILE_FORMAT_OR_VERSION")
        return {"quota": values[0], "period": values[1]}
    if value != "max" and not value.isdigit():
        raise ProbeError("CGROUP_FILE_FORMAT_OR_VERSION")
    if len(value) > 32:
        raise ProbeError("CGROUP_FILE_FORMAT_OR_VERSION")
    return value


def _observe_cgroup(path, mounts, add_gap):
    observation = {"path": path, "files": {}, "delegation_sufficient": False,
                   "write_test_performed": False, "filesystem_verified": False}
    descriptor = None
    try:
        mount = match_mount(path, mounts)
        if mount is None or mount["type"] != "cgroup2":
            add_gap("CGROUP_NOT_CGROUP2", "cgroups", "BLOCKED")
            return observation
        descriptor = _directory_fd(path)
        actual_mount_id = _fd_mount_id(descriptor)
        if actual_mount_id != mount["mount_id"]:
            raise ProbeError("CGROUP_MOUNT_BINDING_CHANGED")
        info = os.fstat(descriptor)
        observation.update(filesystem_verified=True, mount=mount, actual_mount_id=actual_mount_id,
            directory_identity={"device": info.st_dev, "inode": info.st_ino, "uid": info.st_uid,
                                "gid": info.st_gid, "mode": stat.S_IMODE(info.st_mode)})
        # Kernel hierarchy roots do not expose the non-root type/events or
        # resource-limit interfaces. Their absence is not a host failure.
        names = ("cgroup.controllers", "cgroup.subtree_control", "cgroup.max.depth", "cgroup.max.descendants") if path == "/sys/fs/cgroup" else _CGROUP_FILES
        for name in names:
            child = None
            try:
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0), dir_fd=descriptor)
                if _fd_mount_id(child) != actual_mount_id:
                    raise ProbeError("CGROUP_FILE_OVERMOUNT")
                observation["files"][name] = _cgroup_value(name, _read_fd(child, 4096))
            except Exception as error:
                add_gap(getattr(error, "code", "CGROUP_FILE_UNOBSERVED"), "cgroups", detail=name, error=error)
            finally:
                if child is not None:
                    os.close(child)
        if _fd_mount_id(descriptor) != actual_mount_id:
            raise ProbeError("CGROUP_MOUNT_BINDING_CHANGED")
        available = observation["files"].get("cgroup.controllers")
        enabled = observation["files"].get("cgroup.subtree_control")
        if available is not None and not _REQUIRED_CONTROLLERS <= set(available):
            add_gap("REQUIRED_CONTROLLERS_UNAVAILABLE", "cgroups", "BLOCKED")
        if enabled is not None and not _REQUIRED_CONTROLLERS <= set(enabled):
            add_gap("REQUIRED_CONTROLLERS_NOT_ENABLED", "cgroups", "BLOCKED")
        if mount["read_only"]:
            add_gap("CGROUP_MOUNT_READ_ONLY", "cgroups", "BLOCKED")
    except Exception as error:
        add_gap(getattr(error, "code", "CGROUP_OBSERVATION_FAILED"), "cgroups", error=error)
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return observation


def _properties(raw, allowed):
    result = {}
    for line in raw.decode("utf-8", "strict").splitlines():
        key, value = line.split("=", 1)
        if key not in allowed or key in result:
            raise ProbeError("SYSTEMD_PROPERTY_FORMAT_OR_VERSION")
        result[key] = value
    if set(result) != set(allowed):
        raise ProbeError("SYSTEMD_PROPERTIES_INCOMPLETE")
    output = {}
    for key, value in result.items():
        if key == "Version":
            found = re.match(r"^([0-9]{1,6})(?:[.\s+-]|$)", value)
            if not found:
                raise ProbeError("SYSTEMD_VERSION_UNPARSED")
            output[key] = int(found.group(1))
        elif key == "ControlGroup":
            output[key] = _canonical_path(value) if value else None
        elif key == "Id":
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,200}\.slice", value) is None:
                raise ProbeError("SLICE_IDENTITY_UNPARSED")
            output[key] = value
        else:
            enums = {"SystemState": ("initializing", "starting", "running", "degraded", "maintenance", "stopping", "offline", "unknown"),
                "LoadState": ("stub", "loaded", "not-found", "bad-setting", "error", "merged", "masked"),
                "ActiveState": ("active", "reloading", "inactive", "failed", "activating", "deactivating", "maintenance", "refreshing"),
                "SubState": ("active", "dead", "failed"),
                "CPUAccounting": ("yes", "no"), "MemoryAccounting": ("yes", "no"), "TasksAccounting": ("yes", "no")}
            if value not in enums[key]:
                raise ProbeError("SYSTEMD_PROPERTY_FORMAT_OR_VERSION")
            output[key] = value
    return output


def _systemd_observations(args, euid, add_gap):
    environment = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C", "XDG_RUNTIME_DIR": "/run/user/" + str(euid)}
    manager_properties = ("Version", "ControlGroup", "SystemState")
    slice_properties = ("Id", "LoadState", "ActiveState", "SubState", "ControlGroup", "CPUAccounting", "MemoryAccounting", "TasksAccounting")
    commands = [("systemctl_version", ["/usr/bin/systemctl", "--version"], None),
                ("systemd_run_version", ["/usr/bin/systemd-run", "--version"], None),
                ("user_manager", ["/usr/bin/systemctl", "--user", "show", "--property=" + ",".join(manager_properties)], manager_properties)]
    if args.slice:
        commands.append(("slice", ["/usr/bin/systemctl", "--user", "show", args.slice, "--property=" + ",".join(slice_properties)], slice_properties))
    output = {}
    for name, argv, properties in commands:
        captured = _capture(argv, environment)
        row = {key: value for key, value in captured.items() if key != "stdout"}
        output[name] = row
        if captured["status"] != "COMPLETED" or captured["exit_code"] != 0:
            add_gap("SYSTEMD_COMMAND_UNOBSERVED", "systemd", detail=name)
            if captured["cleanup"] != "CONFIRMED":
                add_gap("COMMAND_CLEANUP_UNRESOLVED", "systemd", detail=name)
                break
            continue
        try:
            if properties:
                row["properties"] = _properties(captured["stdout"], properties)
            else:
                match = re.match(rb"systemd ([0-9]{1,6})(?:[\s.]|$)", captured["stdout"])
                if not match:
                    raise ProbeError("SYSTEMD_VERSION_UNPARSED")
                row["version"] = int(match.group(1))
        except Exception as error:
            add_gap(getattr(error, "code", "SYSTEMD_RESPONSE_UNPARSED"), "systemd", detail=name, error=error)
    sliced = output.get("slice", {}).get("properties")
    if sliced:
        if sliced["Id"] != args.slice or sliced["LoadState"] != "loaded" or sliced["ActiveState"] != "active":
            add_gap("SLICE_NOT_ACTIVE_OR_IDENTITY_DIFFERS", "systemd", "BLOCKED")
        if sliced["ControlGroup"] is None or "/sys/fs/cgroup" + sliced["ControlGroup"] != args.cgroup:
            add_gap("SLICE_CGROUP_BINDING_DIFFERS", "systemd", "BLOCKED")
    manager = output.get("user_manager", {}).get("properties")
    if manager and manager["SystemState"] not in ("running", "degraded"):
        add_gap("USER_MANAGER_NOT_RUNNING", "systemd", "BLOCKED")
    versions = [row["version"] for row in output.values() if "version" in row]
    if manager:
        versions.append(manager["Version"])
    if len(set(versions)) > 1:
        add_gap("SYSTEMD_VERSION_MISMATCH", "systemd")
    return output


def probe(args):
    report = {"schema_version": SCHEMA_VERSION, "label": args.label, "readiness": "INCOMPLETE",
        "source_sha256": None,
        "real_e3_accepted": False, "production_supported": False, "business_authorized": False,
        "unverified_blockers": list(UNVERIFIED_BLOCKERS), "gaps": [], "observations": {},
        "semantics": {"exit_zero": "REPORT_GENERATED_ONLY", "quota_syscall_performed": False,
            "service_mutation_performed": False, "mount_targets_accessed": False,
            "real_harness_run": False, "product_python_minimum": [3, 12],
            "quota_permission_model": "HOST_CAP_SYS_ADMIN_VS_PRIVATEUSERS_REQUIRES_REVIEW"}}
    def gap(code, component, severity="INCOMPLETE", *, detail=None, error=None):
        value = {"code": code, "component": component, "severity": severity}
        if detail is not None:
            value["detail"] = detail
        if error is not None:
            value["error_type"] = type(error).__name__
            if isinstance(error, OSError):
                value["errno"] = error.errno
        if value not in report["gaps"]:
            report["gaps"].append(value)
    try:
        # A fingerprint of observed source bytes, not an assertion that host
        # observations or a deployment were accepted. No repository scan.
        report["source_sha256"] = hashlib.sha256(read_bounded(os.path.abspath(__file__), MAX_FILE_BYTES)).hexdigest()
    except Exception as error:
        gap(getattr(error, "code", "PROBE_SOURCE_UNOBSERVED"), "probe", error=error)
    host = {"platform": sys.platform, "python": list(sys.version_info[:3]), "boot_id": None,
            "product_python_satisfied": sys.version_info[:2] >= (3, 12)}
    report["observations"]["host"] = host
    try:
        uname = os.uname()
        host.update(machine=uname.machine, kernel_release=uname.release, kernel_sysname=uname.sysname)
    except Exception as error:
        gap("UNAME_UNOBSERVED", "host", error=error)
    if not host["product_python_satisfied"]:
        gap("PRODUCT_PYTHON_TOO_OLD", "host", "BLOCKED")
    if sys.platform != "linux":
        gap("LINUX_REQUIRED", "host", "BLOCKED")
    uid = os.getuid() if hasattr(os, "getuid") else None
    euid = os.geteuid() if hasattr(os, "geteuid") else None
    identity = {"uid": uid, "euid": euid, "expected_uid": args.expected_uid,
                "expected_uid_matches": None if args.expected_uid is None else uid == euid == args.expected_uid,
                "is_root": euid == 0}
    report["observations"]["identity"] = identity
    if args.expected_uid is None:
        gap("EXPECTED_UID_REQUIRED", "identity")
    elif identity["expected_uid_matches"] is not True:
        gap("EXPECTED_UID_DIFFERS", "identity", "BLOCKED")
    if euid == 0 or uid != euid:
        gap("DEDICATED_NONROOT_ACCOUNT_REQUIRED", "identity", "BLOCKED")
    if not args.cgroup:
        gap("PRIVATE_CGROUP_AND_SLICE_REQUIRED", "cgroups")
    report["observations"].update(namespaces={}, cgroups={}, mounts=[], systemd={})
    if sys.platform == "linux":
        proc = "/proc/" + str(os.getpid())
        try:
            raw_boot = read_bounded("/proc/sys/kernel/random/boot_id", 64)
            if re.fullmatch(rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\n?", raw_boot) is None:
                raise ProbeError("BOOT_ID_FORMAT")
            host["boot_id"] = raw_boot.decode("ascii").removesuffix("\n")
        except Exception as error:
            gap(getattr(error, "code", "BOOT_ID_UNOBSERVED"), "host", error=error)
        try:
            pid1 = read_bounded("/proc/1/comm", 256).decode("ascii", "strict").strip()
            host["pid1_is_systemd"] = pid1 == "systemd"
            # Only the positive fixed name is exposed; other process names can
            # themselves be private host/application identifiers.
            host["pid1_comm"] = "systemd" if pid1 == "systemd" else "OTHER"
            if pid1 != "systemd":
                gap("PID1_NOT_SYSTEMD", "host", "BLOCKED")
        except Exception as error:
            gap(getattr(error, "code", "PID1_UNOBSERVED"), "host", error=error)
        for name in ("mnt", "user"):
            try:
                # Namespace entries are deliberate kernel identity symlinks;
                # they are readlink observations, never followed as files.
                value = os.readlink(proc + "/ns/" + name)
                if re.fullmatch(name + r":\[[0-9]{1,24}\]", value) is None:
                    raise ProbeError("NAMESPACE_IDENTITY_UNPARSED")
                report["observations"]["namespaces"][name] = value
            except Exception as error:
                gap(getattr(error, "code", "NAMESPACE_UNOBSERVED"), "namespaces", detail=name, error=error)
        mounts = []
        try:
            mounts = parse_mountinfo(read_bounded(proc + "/mountinfo", MAX_FILE_BYTES))
        except Exception as error:
            gap(getattr(error, "code", "MOUNTINFO_UNOBSERVED"), "mounts", error=error)
        for target in args.mount_target:
            try:
                mount = match_mount(target, mounts)
                report["observations"]["mounts"].append({"target": target, "match": mount,
                    "existence_verified": False, "writability_verified": False, "hard_quota_verified": False})
                if mount is None:
                    gap("MOUNT_TARGET_UNMATCHED", "mounts")
            except Exception as error:
                gap(getattr(error, "code", "MOUNT_TARGET_UNOBSERVED"), "mounts", error=error)
        groups = report["observations"]["cgroups"]
        try:
            raw = read_bounded(proc + "/cgroup", 16384)
            unified = []
            for line in raw.decode("utf-8", "strict").splitlines():
                hierarchy, controllers, path = line.split(":", 2)
                if not hierarchy.isdigit():
                    raise ProbeError("SELF_CGROUP_FORMAT")
                if hierarchy == "0" and controllers == "":
                    unified.append(_canonical_path(path))
            if len(unified) != 1:
                gap("UNIFIED_SELF_CGROUP_UNRESOLVED", "cgroups")
            else:
                groups["self_unified_path"] = unified[0]
        except Exception as error:
            gap(getattr(error, "code", "SELF_CGROUP_UNOBSERVED"), "cgroups", error=error)
        if mounts:
            groups["root"] = _observe_cgroup("/sys/fs/cgroup", mounts, gap)
            if args.cgroup:
                groups["requested"] = _observe_cgroup(args.cgroup, mounts, gap)
                if args.cgroup == "/sys/fs/cgroup":
                    gap("CGROUP_ROOT_IS_NOT_PRIVATE_DELEGATION", "cgroups", "BLOCKED")
        if euid is not None:
            report["observations"]["systemd"] = _systemd_observations(args, euid, gap)
    if any(item["severity"] == "BLOCKED" for item in report["gaps"]):
        report["readiness"] = "BLOCKED"
    elif report["gaps"]:
        report["readiness"] = "INCOMPLETE"
    else:
        report["readiness"] = "OBSERVED_NOT_ACCEPTED"
    return report


def main(argv=None):
    args = parse_args(argv)
    try:
        report = probe(args)
        raw = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
        if len(raw) + 1 > MAX_REPORT_BYTES:
            raise ProbeError("REPORT_BYTE_LIMIT")
    except Exception as error:
        report = {"schema_version": SCHEMA_VERSION, "label": args.label, "readiness": "INCOMPLETE",
            "source_sha256": None,
            "real_e3_accepted": False, "production_supported": False, "business_authorized": False,
            "unverified_blockers": list(UNVERIFIED_BLOCKERS), "observations": {},
            "gaps": [{"code": getattr(error, "code", "PROBE_OBSERVATION_FAILED"), "component": "probe",
                      "severity": "INCOMPLETE", "error_type": type(error).__name__}]}
        raw = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    sys.stdout.write(raw.decode("ascii") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
