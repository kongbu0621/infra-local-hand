"""The approved eleven-object local observation, with no execution or writes.

Source derivation completes before host observations. Every ordinary object is
read once, with an independent actual-read budget; metadata checks never reread
content. This module has no CLI or caller-selected path/command interface.
"""
from __future__ import annotations

import base64
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import time


def helper(name):
    spec = importlib.util.spec_from_file_location("_local_source_observe_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = helper("q2_local_source_contract")
io = helper("q2_reconciliation_io")
kernel = helper("q2_host_kernel_facts")
NS = 10**9
FS_IOC_GETFLAGS = 0x80086601
WINDOW_FIELDS = {"issued_ns", "deadline_ns", "boottime_issued_ns", "boottime_deadline_ns"}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def _error(error):
    reason = str(error) if isinstance(error, ValueError) else type(error).__name__
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", reason):
        reason = type(error).__name__
    system_error = error
    # Retain an underlying syscall errno when a fixed protection reason wraps
    # it. No raw exception text, paths or substitute data are introduced.
    for _ in range(4):
        if getattr(system_error, "errno", None) is not None:
            break
        cause = system_error.__cause__ or system_error.__context__
        if cause is None:
            break
        system_error = cause
    return dict(reason=reason, error_type=type(error).__name__, errno=getattr(system_error, "errno", None))


def identity():
    require(all(hasattr(os, name) for name in ("getresuid", "getresgid", "getgroups")),
        "LOCAL_SOURCE_IDENTITY_UNSUPPORTED")
    uid, gid, groups = list(os.getresuid()), list(os.getresgid()), sorted(os.getgroups())
    require(len(uid) == len(gid) == 3 and all(type(x) is int and 0 <= x <= 2**32 - 2
        for x in uid + gid + groups) and len(groups) <= 65536,
        "LOCAL_SOURCE_IDENTITY_FORMAT")
    require(uid[0] == uid[1] == uid[2] and uid[0] != 0 and gid[0] == gid[1] == gid[2],
        "LOCAL_SOURCE_ORDINARY_IDENTITY_REQUIRED")
    return dict(uid=uid, gid=gid, supplementary_groups=groups)


class Window:
    """A view of the receiver's original window; never creates a fresh origin."""
    def __init__(self, fields):
        require(type(fields) is dict and set(fields) == WINDOW_FIELDS and
            all(type(value) is int and 0 < value < 2**63 for value in fields.values()),
            "LOCAL_SOURCE_ORIGINAL_WINDOW")
        require(fields["deadline_ns"] == fields["issued_ns"] + 300 * NS and
            fields["boottime_deadline_ns"] == fields["boottime_issued_ns"] + 300 * NS,
            "LOCAL_SOURCE_ORIGINAL_WINDOW")
        self.fields = dict(fields)
        self.last = None
        self.guard()

    def sample(self):
        return dict(monotonic_ns=time.monotonic_ns(),
            boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME))

    def guard(self):
        now = self.sample()
        mono, boot = now["monotonic_ns"], now["boottime_ns"]
        a, b = self.fields["issued_ns"], self.fields["boottime_issued_ns"]
        require(mono >= a and boot >= b and (self.last is None or
            (mono >= self.last["monotonic_ns"] and boot >= self.last["boottime_ns"])),
            "LOCAL_SOURCE_CLOCK_ROLLBACK")
        require(mono < a + 140 * NS and boot < b + 140 * NS and
            mono < self.fields["deadline_ns"] and boot < self.fields["boottime_deadline_ns"],
            "LOCAL_SOURCE_ORIGINAL_WINDOW_EXPIRED")
        require(abs((boot - b) - (mono - a)) <= 2 * NS, "LOCAL_SOURCE_CLOCK_DIVERGED")
        self.last = now
        return now


def _binding(value):
    required = {"authority", "implementation_commit", "implementation_tree", "tools_sha256",
        "package_sha256", "package_bytes", "transport"}
    require(type(value) is dict and set(value) == required, "LOCAL_SOURCE_BINDING")
    for key, length in (("implementation_commit", 40), ("implementation_tree", 40),
                        ("tools_sha256", 64), ("package_sha256", 64)):
        require(type(value[key]) is str and re.fullmatch("[0-9a-f]{" + str(length) + "}", value[key]),
            "LOCAL_SOURCE_BINDING_DIGEST")
    authority = value["authority"]
    require(type(authority) is dict and set(authority) ==
        {"rule", "baseline", "closure", "owner_decision", "scope"} and
        authority["rule"] == c.RULE and authority["baseline"] == c.BASELINE and
        authority["closure"] == c.CLOSURE and authority["scope"] == c.SCOPE and
        authority["owner_decision"] == c.OWNER_DECISION,
        "LOCAL_SOURCE_AUTHORITY")
    transport = value["transport"]
    require(type(transport) is dict and set(transport) == {"receiver_source_sha256",
        "receiver_command_bytes", "frame_bytes", "payload_input_bytes", "package_bytes", "package_sha256"},
        "LOCAL_SOURCE_TRANSPORT_BINDING")
    require(type(transport["receiver_source_sha256"]) is str and
        re.fullmatch("[0-9a-f]{64}", transport["receiver_source_sha256"]), "LOCAL_SOURCE_RECEIVER_DIGEST")
    for key in ("receiver_command_bytes", "frame_bytes", "payload_input_bytes", "package_bytes"):
        require(type(transport[key]) is int and 0 < transport[key] <= c.INPUT_LIMIT,
            "LOCAL_SOURCE_INPUT_LIMIT")
    require(transport["receiver_command_bytes"] + transport["frame_bytes"] ==
        transport["payload_input_bytes"] and type(value["package_bytes"]) is int and
        value["package_bytes"] == transport["package_bytes"] and
        value["package_sha256"] == transport["package_sha256"], "LOCAL_SOURCE_TRANSPORT_BINDING")
    require(len(encoded(value)) <= 16384, "LOCAL_SOURCE_BINDING_LIMIT")
    return json.loads(encoded(value))


def _acl(fd, guard):
    for name in ("system.posix_acl_access", "system.posix_acl_default"):
        guard()
        try:
            os.getxattr(fd, name)
        except OSError as error:
            require(error.errno == errno.ENODATA, "LOCAL_SOURCE_ACL_UNSUPPORTED")
        else:
            raise ValueError("LOCAL_SOURCE_ACL_PRESENT")


def _chain(held, guard):
    """The approved preflight metadata-only ancestor ACL flow, no enumeration."""
    held.verify()
    for _, fd, before in held.chain:
        guard()
        opened = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        try:
            guard()
            current = io.metadata(os.fstat(opened))
            require(all(current[key] == before[key] for key in io.ANCESTOR_FIELDS),
                "LOCAL_SOURCE_ANCESTOR_CHANGED")
            _acl(opened, guard)
            guard()
            require(io.metadata(os.fstat(opened)) == current, "LOCAL_SOURCE_ANCESTOR_METADATA_CHANGED")
        finally:
            os.close(opened)
    held.verify()


def _retained_parent_failure(held, path, role):
    """Describe only metadata already retained by a failed HeldPath init.

    Failed initialization has closed its descriptors; this function performs no
    filesystem operation. The root handle is special: HeldPath stores one fstat
    result and protects a second, so its retained metadata is not necessarily
    the exact failed check input. Later components protect the stored result.
    """
    if role not in ("host_parent", "control_parent"):
        return None
    chain = held.chain
    parts = Path(path).parts
    if type(chain) is not list or not chain or len(chain) > len(parts):
        return None
    index = len(chain) - 1
    if any(type(item) is not tuple or len(item) != 3 or
        item[0] != (None if offset == 0 else parts[offset]) for offset, item in enumerate(chain)):
        return None
    before = chain[-1][2]
    if type(before) is not dict or set(before) != set(io.META_FIELDS) or not all(
        type(before[key]) is int for key in io.META_FIELDS):
        return None
    owners = sorted(held.allowed_uids)
    if not 1 <= len(owners) <= 2 or any(type(uid) is not int for uid in owners):
        return None
    value = dict(parent_role=role, component_index=index,
        component_kind="root" if index == 0 else "parent" if len(chain) == len(parts) else "ancestor",
        component_path=str(Path(*parts[:index + 1])),
        reason="RECONCILIATION_UNPROTECTED_PATH", allowed_uids=owners, forbidden_mode_mask=0o6022,
        retained_metadata={key: before[key] for key in io.META_FIELDS},
        metadata_source="HELD_PATH_INITIALIZATION_RETAINED_METADATA",
        metadata_is_exact_check_input=index > 0, additional_filesystem_observation=False)
    if index > 0:
        failures = []
        if before["uid"] not in owners:
            failures.append("OWNER_NOT_ALLOWED")
        if before["st_mode"] & 0o6022:
            failures.append("FORBIDDEN_MODE_BITS")
        if not failures:
            return None
        value["failed_checks"] = failures
    else:
        value["metadata_limitation"] = "ROOT_PROTECTION_USED_A_SEPARATE_FSTAT_RESULT"
    return value if len(encoded(value)) <= 8192 else None


def _hold_parent(path, role, guard, owners, report):
    # Keep the partially initialized instance without changing HeldPath's
    # syscall order, protection predicates, exception or cleanup behavior.
    held = object.__new__(io.HeldPath)
    try:
        io.HeldPath.__init__(held, path, guard, directory=True, allowed_uids=owners)
    except BaseException as error:
        if type(error) is ValueError and str(error) == "RECONCILIATION_UNPROTECTED_PATH":
            try:
                detail = _retained_parent_failure(held, path, role)
                if detail is not None:
                    report["parent_protection_failure"] = detail
            except BaseException:
                # Diagnostics are subordinate to the original failure. They
                # cannot replace its reason or cause a retry/new observation.
                pass
        raise
    return held


def _marker(parent, name, guard, report, phase):
    value = dict(phase=phase, state="UNCERTAIN")
    report["marker_observations"].append(value)
    parent.verify(); guard()
    try:
        os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
    except FileNotFoundError:
        parent.verify(); guard()
        # A second lookup after the held-chain check discloses a stable ENOENT.
        try:
            os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        except FileNotFoundError:
            parent.verify()
            value["state"] = "ABSENT_AT_OBSERVATION"
            return
    value["state"] = "EXISTING_PATH_BLOCKED"
    raise ValueError("LOCAL_SOURCE_ALREADY_CONSUMED_OR_UNCERTAIN")


def _kernel(kind, guard, report):
    require(len(report["kernel_reads"]) < 3, "LOCAL_SOURCE_KERNEL_READ_COUNT")
    detail = {}
    report["kernel_reads"].append(detail)
    try:
        return kernel.read_fact(kind, guard, detail)
    finally:
        report["byte_counts"]["kernel_actual_read"] = sum(
            row.get("bytes_observed", 0) for row in report["kernel_reads"])
        require(report["byte_counts"]["kernel_actual_read"] <= c.KERNEL_READ_LIMIT,
            "LOCAL_SOURCE_KERNEL_READ_LIMIT")


def _boot(guard, report, expected):
    raw = _kernel("boot", guard, report)
    require(raw == (expected + "\n").encode("ascii"), "LOCAL_SOURCE_BOOT_CHANGED")


def _mounts(raw):
    def unescape(value):
        value = re.sub(r"\\(040|011|012|134)", lambda item: chr(int(item[1], 8)), value)
        require("\0" not in value, "LOCAL_SOURCE_MOUNTINFO")
        return value
    rows = []
    for line in raw.decode("utf-8", "strict").splitlines():
        fields = line.split(" ")
        require("-" in fields, "LOCAL_SOURCE_MOUNTINFO")
        split = fields.index("-")
        require(split >= 6 and len(fields) == split + 4 and fields[0].isdigit()
            and fields[1].isdigit() and re.fullmatch(r"\d+:\d+", fields[2]), "LOCAL_SOURCE_MOUNTINFO")
        point = unescape(fields[4])
        require(point.startswith("/"), "LOCAL_SOURCE_MOUNTINFO")
        rows.append(dict(mount_id=int(fields[0]), parent_mount_id=int(fields[1]), device=fields[2],
            root=unescape(fields[3]), mountpoint=point, mount_options=fields[5].split(","),
            optional_fields=fields[6:split], filesystem=fields[split + 1],
            source=unescape(fields[split + 2]), super_options=fields[split + 3].split(",")))
    return rows


def _filesystem(parent, mounts, guard):
    matches = [row for row in mounts if parent.path == row["mountpoint"] or
        parent.path.startswith(row["mountpoint"].rstrip("/") + "/")]
    require(matches, "LOCAL_SOURCE_MOUNT_NOT_FOUND")
    longest = max(len(row["mountpoint"]) for row in matches)
    selected = [row for row in matches if len(row["mountpoint"]) == longest]
    require(len(selected) == 1, "LOCAL_SOURCE_MOUNT_AMBIGUOUS")
    parent.verify(); guard()
    before = io.metadata(os.fstat(parent.fd))
    require(selected[0]["device"] == str(os.major(before["device"])) + ":" +
        str(os.minor(before["device"])), "LOCAL_SOURCE_MOUNT_DEVICE")
    guard()
    try:
        values = os.fstatvfs(parent.fd)
    except OSError as error:
        if error.errno not in (errno.ENOTTY, errno.EOPNOTSUPP, errno.EINVAL, errno.ENOSYS):
            raise
        capacity = dict(status="UNSUPPORTED", errno=error.errno)
    else:
        capacity = {key: getattr(values, key) for key in ("f_bsize", "f_frsize", "f_blocks", "f_bfree",
            "f_bavail", "f_files", "f_ffree", "f_favail", "f_flag")}
        require(all(type(value) is int and value >= 0 for value in capacity.values()), "LOCAL_SOURCE_STATVFS")
        capacity.update(status="OBSERVED", available_bytes=values.f_bavail * values.f_frsize,
            available_inodes=values.f_favail)
    guard()
    try:
        flags = dict(status="OBSERVED", value=struct.unpack("I", fcntl.ioctl(parent.fd,
            FS_IOC_GETFLAGS, struct.pack("I", 0))[:4])[0])
    except OSError as error:
        if error.errno not in (errno.ENOTTY, errno.EOPNOTSUPP, errno.EINVAL, errno.ENOSYS):
            raise
        flags = dict(status="UNSUPPORTED", errno=error.errno)
    parent.verify()
    return dict(path=parent.path, metadata=before, containing_mount=selected[0], statvfs=capacity,
        parent_flags=flags, allocation_peak_proven=False, durability_proven=False,
        raw_device_read_performed=False)


def _observe_one(target, parent, guard, report, identities):
    row = next(value for value in report["objects"] if value["id"] == target["id"])
    row.update(status="OBSERVING", started=guard(), actual_read_bytes=0)
    name = Path(target["path"]).name
    fd = None
    def check():
        guard(); parent.verify()
    try:
        check()
        try:
            before_stat = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        except FileNotFoundError:
            check()
            try:
                os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
            except FileNotFoundError:
                check()
                row.update(status="CURRENT_MISSING", ended=guard())
                return
            raise ValueError("LOCAL_SOURCE_NAME_CHANGED")
        row["before"] = io.metadata(before_stat)
        io.protected(before_stat, allowed_uids=parent.allowed_uids)
        require(before_stat.st_dev == parent.chain[-1][2]["device"], "LOCAL_SOURCE_FILE_DEVICE")
        key = before_stat.st_dev, before_stat.st_ino
        require(key not in identities, "LOCAL_SOURCE_OBJECT_ALIAS")
        check(); fd = os.open(name, io.flags(), dir_fd=parent.fd)
        check()
        require(io.metadata(os.fstat(fd)) == row["before"], "LOCAL_SOURCE_NAME_CHANGED")
        _acl(fd, check)
        identities.add(key)
        if before_stat.st_size != target["size_cap"]:
            outcome = "CURRENT_LENGTH_CHANGED"
            raw, observed_sha256, matches_source = None, None, None
        else:
            digest, pieces, total = hashlib.sha256(), [], 0
            while True:
                check()
                block = os.read(fd, min(65536, target["size_cap"] + 1 - total))
                total += len(block)
                row["actual_read_bytes"] = total
                report["byte_counts"]["ordinary_actual_read"] += len(block)
                require(report["byte_counts"]["ordinary_actual_read"] <= c.READ_LIMIT,
                    "LOCAL_SOURCE_READ_LIMIT")
                require(total <= target["size_cap"], "LOCAL_SOURCE_LONG_READ")
                if not block:
                    break
                digest.update(block)
                if target["return_raw"]:
                    pieces.append(block)
            require(total == target["size_cap"], "LOCAL_SOURCE_SHORT_READ")
            observed_sha256 = digest.hexdigest()
            matches_source = observed_sha256 == target["sha256"]
            raw = b"".join(pieces) if target["return_raw"] and matches_source else None
            outcome = "MATCHED" if matches_source else "CURRENT_DIGEST_CHANGED"
        check(); _acl(fd, check); check()
        row["after"] = io.metadata(os.fstat(fd))
        require(row["after"] == row["before"] and
            io.metadata(os.stat(name, dir_fd=parent.fd, follow_symlinks=False)) == row["before"],
            "LOCAL_SOURCE_METADATA_OR_NAME_CHANGED")
        check()
        row.update(status=outcome, ended=guard(), metadata_stable=True,
            allocated_bytes=before_stat.st_blocks * 512, observed_inode_count=1)
        if observed_sha256 is not None:
            row.update(observed_sha256=observed_sha256, sha256_matches_source=matches_source)
        if raw is not None:
            row["raw_base64"] = base64.b64encode(raw).decode("ascii")
        require(len(encoded(report)) <= c.REPORT_LIMIT, "LOCAL_SOURCE_REPORT_LIMIT")
        check()
    except BaseException as error:
        row.pop("raw_base64", None)
        row.pop("observed_sha256", None)
        row.pop("sha256_matches_source", None)
        row.update(status="BLOCKED", error=_error(error))
        raise
    finally:
        if fd is not None:
            os.close(fd)


def _finish(report, window, guard):
    """Encoding is inside the original budget, including its own final check."""
    completed = [row for row in report["objects"] if row["status"] in
        ("MATCHED", "CURRENT_MISSING", "CURRENT_LENGTH_CHANGED", "CURRENT_DIGEST_CHANGED")]
    stable = [row for row in completed if row.get("metadata_stable")]
    report["completion"] = dict(attempted=sum(row["status"] != "NOT_ATTEMPTED" for row in report["objects"]),
        observed=len(completed), matched=sum(row["status"] == "MATCHED" for row in completed),
        raw_returned=sum("raw_base64" in row for row in completed), expected_objects=11)
    report["current_observed_totals"] = dict(allocated_bytes=sum(row["allocated_bytes"] for row in stable),
        inode_count=len(stable), includes_only_stable_observed_objects=True,
        scope="THIS_INVOCATION_STABLE_TARGET_FILES_ONLY", parent_directories_included=False,
        complete_inventory=False, atomic_snapshot=False, unknown_objects_excluded=True)
    report["ended"] = window.sample() if window is not None else None
    try:
        if guard is not None:
            guard()
        for _ in range(5):
            size = len(encoded(report))
            if report["byte_counts"]["output_json_bytes"] == size:
                break
            report["byte_counts"]["output_json_bytes"] = size
        require(size <= c.REPORT_LIMIT, "LOCAL_SOURCE_REPORT_LIMIT")
        if guard is not None:
            guard()
        return report
    except BaseException as error:
        report.update(status="LOCAL_SOURCE_EVIDENCE_BLOCKED", error=_error(error))
        if len(encoded(report)) > c.REPORT_LIMIT:
            report["objects"] = [dict(id=row["id"], status=row["status"], raw_omitted="raw_base64" in row,
                actual_read_bytes=row.get("actual_read_bytes")) for row in report["objects"]]
            report["kernel_reads"] = [dict(target=row.get("target"), status=row.get("status"),
                bytes_observed=row.get("bytes_observed")) for row in report["kernel_reads"]]
            report["parent_filesystems"] = []
            report["report_detail_omitted_due_to_limit"] = True
            report["completion"]["raw_returned"] = 0
    # Failure encoding still returns the retained scope; never performs new reads.
    for _ in range(5):
        size = len(encoded(report))
        if report["byte_counts"]["output_json_bytes"] == size:
            break
        report["byte_counts"]["output_json_bytes"] = size
    require(size <= c.REPORT_LIMIT, "LOCAL_SOURCE_REPORT_LIMIT")
    return report


def run_local(carrier_raw, manifest_raw, attestation_raw, *, reception_window, binding):
    report = dict(schema=c.SCHEMA, scope=c.SCOPE, status="LOCAL_SOURCE_EVIDENCE_BLOCKED",
        phase="offline_validation", objects=[], kernel_reads=[], parent_filesystems=[], marker_observations=[],
        byte_counts=dict(payload_input=None, ordinary_actual_read=0, kernel_actual_read=0, output_json_bytes=0),
        allow_consume=False, allow_run=False, wrapper_executed=False, remote_attempted=False,
        host_persistence_attempted=False, window_consumed_by_this_invocation=False,
        q2_accepted=False, q3_accepted=False, production_admitted=False,
        production_accepted=False, production_supported=False,
        k4_trees_reread=False, full_host_inventory_complete=False, historical_identity_adopted=False,
        historical_costs_adopted=False, complete_joint_bill_proven=False, h07_proven=False,
        allocation_peak_proven=False, durability_proven=False,
        namespace_alignment=dict(status="ENVIRONMENT_ASSUMPTION_NOT_PROVEN",
            required="original_host_terminal_and_matching_pid_proc_namespaces", namespace_changed=False))
    parents, window, guard = {}, None, None
    try:
        window = Window(reception_window)
        report["reception_window"] = dict(window.fields)
        report["started"] = window.guard()
        report["binding"] = _binding(binding)
        report["byte_counts"]["payload_input"] = binding["transport"]["payload_input_bytes"]
        derived = c.targets(carrier_raw, manifest_raw, attestation_raw)
        window.guard()
        report.update(sources=derived["sources"], target_manifest_sha256=derived["target_manifest_sha256"])
        report["objects"] = [dict({key: value for key, value in target.items() if key != "sha256"},
            source_sha256=target["sha256"], status="NOT_ATTEMPTED") for target in derived["targets"]]
        report["phase"] = "ordinary_identity"
        original_identity = identity()
        report["identity"] = original_identity
        owners = {0, original_identity["uid"][1]}
        def guard():
            now = window.guard()
            require(identity() == original_identity, "LOCAL_SOURCE_IDENTITY_CHANGED")
            return now
        guard()
        location = derived["location"]
        report["phase"] = "host_boot"
        _boot(guard, report, location["expected_boot_id"])
        report["phase"] = "protected_parents"
        for role in ("host_parent", "control_parent"):
            held = _hold_parent(location[role], role, guard, owners, report)
            parents[role] = held
            _chain(held, guard)
        identities = {(parent.chain[-1][2]["device"], parent.chain[-1][2]["inode"])
            for parent in parents.values()}
        require(len(identities) == 2, "LOCAL_SOURCE_PARENT_ALIAS")
        report["phase"] = "marker_precheck"
        _marker(parents["host_parent"], location["marker_name"], guard, report, "before")
        report["phase"] = "parent_filesystems"
        mounts = _mounts(_kernel("mountinfo", guard, report))
        for parent in parents.values():
            report["parent_filesystems"].append(_filesystem(parent, mounts, guard))
        report["phase"] = "fixed_objects"
        for target in derived["targets"]:
            for parent in parents.values():
                parent.verify()
            parent = parents["host_parent" if target["source"] == "M" else "control_parent"]
            require(target["parent"] == parent.path, "LOCAL_SOURCE_TARGET_PARENT")
            _observe_one(target, parent, guard, report, identities)
        report["phase"] = "final_local_recheck"
        for parent in parents.values():
            _chain(parent, guard)
        _marker(parents["host_parent"], location["marker_name"], guard, report, "after")
        _boot(guard, report, location["expected_boot_id"])
        for parent in parents.values():
            parent.verify()
        guard()
        report["status"] = "OBSERVED_PARTIAL"
    except BaseException as error:
        report["error"] = _error(error)
    finally:
        for parent in reversed(list(parents.values())):
            try:
                parent.close()
            except OSError as error:
                report.update(status="LOCAL_SOURCE_EVIDENCE_BLOCKED", error=_error(error))
    return _finish(report, window, guard if guard is not None else window.guard if window else None)
