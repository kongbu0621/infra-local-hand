"""The approved, local-only LOCAL_PREFLIGHT; no consumption or dispatch path.

The exact private launcher first verifies its complete Git source closure. This
module repeats the original offline input checks before starting a temporary
dual-clock observation. Current observations never adopt historical identity,
establish a joint bill, or authorize the separately blocked execution entry.
"""
from __future__ import annotations

import ast
import copy
import errno
import fcntl
import importlib.util
import os
from pathlib import Path, PurePosixPath as P
import re
import stat
import struct


def helper(name):
    spec = importlib.util.spec_from_file_location("_host_local_preflight_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = helper("q2_host_window_contract")
io = helper("q2_reconciliation_io")
delivery = helper("q2_reconciliation_delivery")
require = c.require
SCHEMA = "local-hand-q2-host-window-local-preflight/v1"
LOCATOR_SHA256 = "7672ac050609fc7e05481443c9239df0d36f25b4ec9860c2bb833024b962647a"
LOCATOR_BYTES = 50266
CAPTURE_PROOF_SHA256 = "12f6e18bf2858451c0bffb5aa730f4b59d4c713fcdbf0cd251221e1bc2d63fd2"
CAPTURE_PROOF_BYTES = 15576
OUTPUT_LIMIT = 2 * 1024**2
REPORT_LIMIT = OUTPUT_LIMIT - 16384  # original receiver/protocol/error output
MAX_ENTRIES = 512
MAX_READ_BYTES = 64 * 1024**2
KERNEL_LIMIT = 1024**2
FS_IOC_GETFLAGS = 0x80086601
MISSING = ("HOST_HISTORICAL_FUTURE_SOURCE_COVERAGE", "HOST_OBJECT_COST_CLASSIFICATION",
    "NATIVE_AUDIT_SOURCE_BOUND", "WRAPPER_AUTHORIZED_SOURCE_AND_EXECUTION_BINDING",
    "REMOTE_ABSOLUTE_DEADLINE_AND_STOP_COVERAGE", "COMPLETE_GUEST_JOINT_ADMISSION",
    "HOST_ALLOCATION_PEAK_AND_DURABILITY_QUALIFICATION")


def targets(carrier_raw, host_attestation_raw, host_source_proof, *, config=None):
    """Fixed inspection locators; the return manifest is NOT a history baseline."""
    location = c.sources(carrier_raw, host_attestation_raw)
    c.keys(host_source_proof, ("host_manifest_raw", "original_capture_proof_raw"))
    raw = host_source_proof["host_manifest_raw"]
    require(type(raw) is bytes and len(raw) == LOCATOR_BYTES and c.sha(raw) == LOCATOR_SHA256,
        "HOST_LOCAL_LOCATOR_PIN")
    manifest = c.document(raw, limit=LOCATOR_BYTES)
    proof_raw = host_source_proof["original_capture_proof_raw"]
    require(type(proof_raw) is bytes and len(proof_raw) == CAPTURE_PROOF_BYTES
        and c.sha(proof_raw) == CAPTURE_PROOF_SHA256, "HOST_LOCAL_CAPTURE_PROOF_PIN")
    proof = c.document(proof_raw, limit=CAPTURE_PROOF_BYTES)
    constants = {}
    for node in ast.parse(carrier_raw).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in ("HOST_RESULT", "HOST_OLD", "OLD_HOST_FILES"):
                require(target.id not in constants, "HOST_LOCAL_CARRIER_CONSTANT")
                constants[target.id] = ast.literal_eval(node.value)
    require(set(constants) == {"HOST_RESULT", "HOST_OLD", "OLD_HOST_FILES"}, "HOST_LOCAL_CARRIER_CONSTANT")
    old_root, retry_root = c.path(constants["HOST_OLD"]), c.path(constants["HOST_RESULT"])
    pins = constants["OLD_HOST_FILES"]
    require(type(pins) is dict and len(pins) == 7, "HOST_LOCAL_OLD_PINS")
    for name, digest in pins.items():
        require(type(name) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", name),
            "HOST_LOCAL_OLD_PIN_PATH")
        c.digest(digest)
    require(pins.get("original-capture-proof.json") == CAPTURE_PROOF_SHA256,
        "HOST_LOCAL_CAPTURE_PROOF_BINDING")
    prep_root = c.path(proof["directory"]["path"])
    rows = manifest["entries"]
    require(type(rows) is list and len(rows) == manifest["entry_count"] == 49, "HOST_LOCAL_LOCATOR_MEMBERS")
    roots, siblings, paths = set(), [], set()
    for row in rows:
        name = c.path(row["source_path"])
        require(name not in paths and row["source_metadata"]["path"] == name
            and name.startswith(location["parent"] + "/"), "HOST_LOCAL_LOCATOR_PATH")
        paths.add(name)
        require(row["type"] in ("directory", "regular"), "HOST_LOCAL_LOCATOR_TYPE")
        if row["type"] == "directory":
            require(str(P(name).parent) == location["parent"], "HOST_LOCAL_LOCATOR_ROOT")
            roots.add(name)
        elif str(P(name).parent) == location["parent"]:
            siblings.append(name)
    require(len(roots) == 5 and len(siblings) == 7 and
        {old_root, retry_root, prep_root} <= roots, "HOST_LOCAL_LOCATOR_COVERAGE")
    require(all(name in roots or name in siblings or str(P(name).parent) in roots for name in paths),
        "HOST_LOCAL_LOCATOR_COVERAGE")
    old_pins = [{"path": old_root + "/" + name, "sha256": digest} for name, digest in sorted(pins.items())]
    require(all(row["path"] in paths for row in old_pins), "HOST_LOCAL_PIN_LOCATORS")
    if config is not None:
        require(sorted(config["old_host_files"], key=lambda row: row["path"]) == old_pins,
            "HOST_LOCAL_CONFIG_OLD_PINS")
    return dict(location=location, roots=sorted(roots), old_pins=old_pins,
        unobserved_siblings=sorted(siblings), locator_sha256=LOCATOR_SHA256,
        locator_bytes=LOCATOR_BYTES, capture_proof_sha256=CAPTURE_PROOF_SHA256,
        source_role="KNOWN_OBJECT_LOCATOR_ONLY", current_observation_not_adoption=True,
        historical_identity_adopted=False, cost_classification_proven=False,
        locator_only_roots=sorted(roots - {old_root, retry_root, prep_root}))


def encode_report(value):
    return c.encoded(value, limit=REPORT_LIMIT)


def _acl(fd):
    for name in ("system.posix_acl_access", "system.posix_acl_default"):
        try:
            os.getxattr(fd, name)
        except OSError as error:
            require(error.errno == errno.ENODATA, "HOST_LOCAL_ACL_UNSUPPORTED")
        else:
            raise ValueError("HOST_LOCAL_ACL_PRESENT")


def _chain(held, guard):
    held.verify()
    for _, fd, before in held.chain:
        guard()
        # Metadata-only: neither read nor readdir is used on this descriptor.
        # O_NOATIME would needlessly require ownership of root-owned ancestors.
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        opened = os.open(".", flags, dir_fd=fd)
        try:
            current = io.metadata(os.fstat(opened))
            require(all(current[key] == before[key] for key in io.ANCESTOR_FIELDS),
                "HOST_LOCAL_ANCESTOR_CHANGED")
            _acl(opened)
            require(io.metadata(os.fstat(opened)) == current, "HOST_LOCAL_ANCESTOR_METADATA_CHANGED")
        finally:
            os.close(opened)
    held.verify()


def _kernel_text(path, guard, maximum):
    # Root-owned proc leaves may reject O_NOATIME for an ordinary user. That is
    # a supported BLOCK result, not a reason to retry a content read unprotected.
    try:
        with io.HeldPath(path, guard, allowed_uids={0, os.geteuid()}) as held:
            guard()
            raw = os.read(held.fd, maximum + 1)
            require(len(raw) <= maximum and not os.read(held.fd, 1), "HOST_LOCAL_KERNEL_READ_LIMIT")
            held.verify()
            return raw
    except PermissionError as error:
        raise ValueError("HOST_LOCAL_KERNEL_NOATIME_PERMISSION") from error


def _boot(guard):
    raw = _kernel_text("/proc/sys/kernel/random/boot_id", guard, 64)
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "HOST_LOCAL_BOOT_FORMAT")
    return c.boot(raw[:-1].decode("ascii"))


def _marker(parent, report):
    parent.guard()
    try:
        os.stat(c.DIRECTORY_NAME, dir_fd=parent.fd, follow_symlinks=False)
    except FileNotFoundError:
        report["consumption_path_state"] = "ABSENT_AT_OBSERVATION"
        return
    report["consumption_path_state"] = "EXISTING_PATH_BLOCKED"
    raise ValueError("HOST_LOCAL_ALREADY_CONSUMED_OR_UNCERTAIN")


def _mount_observation(parent, guard):
    raw = _kernel_text("/proc/" + str(os.getpid()) + "/mountinfo", guard, KERNEL_LIMIT)
    matches = []
    def unescape(value):
        return re.sub(r"\\(040|011|012|134)", lambda match: chr(int(match[1], 8)), value)
    for line in raw.decode("utf-8", "strict").splitlines():
        fields = line.split(" ")
        require("-" in fields, "HOST_LOCAL_MOUNTINFO")
        split = fields.index("-")
        require(split >= 6 and len(fields) == split + 4, "HOST_LOCAL_MOUNTINFO")
        mountpoint = unescape(fields[4])
        if parent.path == mountpoint or parent.path.startswith(mountpoint.rstrip("/") + "/"):
            matches.append(dict(mount_id=int(fields[0]), parent_mount_id=int(fields[1]),
                device=fields[2], root=unescape(fields[3]), mountpoint=mountpoint,
                mount_options=fields[5].split(","), optional_fields=fields[6:split],
                filesystem=fields[split + 1], source=unescape(fields[split + 2]),
                super_options=fields[split + 3].split(",")))
    require(matches, "HOST_LOCAL_MOUNT_NOT_FOUND")
    matches.sort(key=lambda row: (len(row["mountpoint"]), row["mount_id"]))
    require(len(matches) <= 64, "HOST_LOCAL_MOUNT_LIMIT")
    guard(); values = os.fstatvfs(parent.fd)
    capacity = {key: getattr(values, key) for key in
        ("f_bsize", "f_frsize", "f_blocks", "f_bfree", "f_bavail", "f_files", "f_ffree", "f_favail", "f_flag")}
    require(all(type(value) is int and value >= 0 for value in capacity.values()), "HOST_LOCAL_STATVFS")
    capacity.update(available_bytes=values.f_bavail * values.f_frsize, available_inodes=values.f_favail)
    guard()
    try:
        flags = dict(status="OBSERVED", value=struct.unpack("I", fcntl.ioctl(parent.fd,
            FS_IOC_GETFLAGS, struct.pack("I", 0))[:4])[0])
    except OSError as error:
        flags = dict(status="UNSUPPORTED", errno=error.errno)
    parent.verify()
    return dict(mountinfo_sha256=c.sha(raw), mountinfo_bytes=len(raw), containing_mounts=matches,
        statvfs=capacity, parent_flags=flags, allocation_peak_proven=False, durability_proven=False,
        raw_device_read_performed=False)


def _scan_tree(path, guard, allowed_uids, report, state, old_pins):
    value = dict(path=path, complete=False, entries=[], cost_category="UNPROVEN")
    report["observations"]["trees"].append(value)
    def add(relative, info, kind, **extra):
        guard()
        identity = info.st_dev, info.st_ino
        require(identity not in state["identities"], "HOST_LOCAL_OBJECT_ALIAS")
        require(state["entries"] < MAX_ENTRIES, "HOST_LOCAL_ENTRY_LIMIT")
        state["identities"].add(identity); state["entries"] += 1
        state["allocated"] += info.st_blocks * 512
        value["entries"].append(dict(relative_path=relative, type=kind,
            source_metadata=io.metadata(info), **extra))
        require(len(encode_report(report)) <= OUTPUT_LIMIT - 16384, "HOST_LOCAL_OUTPUT_LIMIT")
    def visit(fd, relative, root_device):
        guard(); before = os.fstat(fd)
        io.protected(before, True, allowed_uids=allowed_uids); _acl(fd)
        names = []
        with os.scandir(fd) as children:
            for child in children:
                guard()
                require(len(names) + state["entries"] < MAX_ENTRIES, "HOST_LOCAL_ENTRY_LIMIT")
                names.append(child.name)
        for name in sorted(names):
            guard()
            rel = name if relative == "." else relative + "/" + name
            c.path(path + "/" + rel)
            before_child = os.stat(name, dir_fd=fd, follow_symlinks=False)
            require(before_child.st_dev == root_device, "HOST_LOCAL_TREE_DEVICE_CHANGED")
            is_directory = stat.S_ISDIR(before_child.st_mode)
            io.protected(before_child, is_directory, allowed_uids=allowed_uids)
            child = os.open(name, io.flags(is_directory), dir_fd=fd)
            try:
                require(io.metadata(os.fstat(child)) == io.metadata(before_child), "HOST_LOCAL_NAME_CHANGED")
                _acl(child)
                if is_directory:
                    visit(child, rel, root_device)
                else:
                    require(0 <= before_child.st_size <= MAX_READ_BYTES - state["read_bytes"],
                        "HOST_LOCAL_READ_LIMIT")
                    digest = io._digest(child, guard, MAX_READ_BYTES - state["read_bytes"])
                    state["read_bytes"] += before_child.st_size
                    full = path + "/" + rel
                    if full in old_pins:
                        require(digest == old_pins[full], "HOST_LOCAL_OLD_PIN_CHANGED")
                        report["observations"]["old_pin_matches"].append(full)
                    add(rel, before_child, "file", sha256=digest)
                require(io.metadata(os.fstat(child)) == io.metadata(before_child)
                    and io.metadata(os.stat(name, dir_fd=fd, follow_symlinks=False)) == io.metadata(before_child),
                    "HOST_LOCAL_METADATA_CHANGED")
            finally:
                os.close(child)
        require(io.metadata(os.fstat(fd)) == io.metadata(before), "HOST_LOCAL_DIRECTORY_CHANGED")
        add(relative, before, "directory")
    with io.HeldPath(path, guard, directory=True, allowed_uids=allowed_uids) as held:
        _chain(held, guard)
        visit(held.fd, ".", os.fstat(held.fd).st_dev)
        held.verify()
    value["entries"].sort(key=lambda row: row["relative_path"])
    value["complete"] = True


def _window(reception_window):
    if reception_window is None:
        return delivery.Window()
    # Only the source-pinned in-memory receiver supplies this internal value.
    # Neither command-line arguments nor the private configuration select time.
    fields = c.validate_window(reception_window)
    value = object.__new__(delivery.Window)
    value.monotonic = delivery.time.monotonic_ns
    value.boottime = lambda: delivery.time.clock_gettime_ns(delivery.time.CLOCK_BOOTTIME)
    for key, number in fields.items():
        setattr(value, key, number)
    value.guard()
    return value


def run_local(config, inputs, carrier_raw, host_attestation_raw, *, host_source_proof,
              reception_window=None):
    """Observe exactly the permitted local precheck and always stop before mkdir.

    This neither executes nor adopts the wrapper. Existing offline plan/config
    pins remain checked, and its historical seven file pins are cross-bound to
    the exact carrier. Missing wrapper/audit/remote facts still block all later
    consumption and dispatch; they do not fabricate local observations.
    """
    report = dict(schema=SCHEMA, scope=c.SCOPE, status="LOCAL_PREFLIGHT_BLOCKED",
        reason="HOST_LOCAL_OFFLINE_INPUTS_REQUIRED", offline_sources_verified=False,
        local_preflight_started=False, field_reads_performed=False,
        consumption_path_state="NOT_OBSERVED", window_consumed_by_this_invocation=False,
        host_persistence_attempted=False, remote_attempted=False, wrapper_executed=False,
        allow_consume=False, allow_run=False, joint_admission_proven=False,
        q2_accepted=False, q3_accepted=False, production_supported=False,
        current_observation_not_adoption=True, missing=list(MISSING), observations={})
    window = None
    stage = "offline_inputs"
    try:
        verified, location = helper("q2_reconciliation_entry").offline_inputs(
            config, inputs, carrier_raw, host_attestation_raw)
        selected = targets(carrier_raw, host_attestation_raw, host_source_proof, config=config)
        require(selected["location"] == location, "HOST_LOCAL_SOURCE_LOCATION")
        report.update(offline_sources_verified=True, implementation_commit=verified.implementation_commit,
            source_tree=verified.execution["source"]["tree"], manifest_sha256=verified.digest,
            target_sources=copy.deepcopy(selected))
        stage = "local_window"
        window = _window(reception_window)
        origin = window.fields()
        def guard():
            require(window.fields() == origin, "HOST_LOCAL_ORIGIN_CHANGED")
            window.guard()
            require(window.remaining_ns(window.issued_ns + 140 * c.NS) > 0, "HOST_LOCAL_PREPARATION_EXPIRED")
        report.update(local_preflight_started=True, window=origin,
            preparation_deadline_ns=window.issued_ns + 140 * c.NS)
        guard(); stage = "host_boot"; report["field_reads_performed"] = True
        observed_boot = _boot(guard)
        report["observations"]["boot_id"] = observed_boot
        require(observed_boot == location["expected_boot_id"], "HOST_LOCAL_BOOT_CHANGED")
        stage = "parent_and_marker"
        allowed_uids = {0, os.geteuid()}
        with io.HeldPath(location["parent"], guard, directory=True, allowed_uids=allowed_uids) as parent:
            _marker(parent, report)
            _chain(parent, guard)
            report["observations"]["parent_metadata"] = io.metadata(os.fstat(parent.fd))
            stage = "filesystem_observation"
            report["observations"]["filesystem"] = _mount_observation(parent, guard)
            report["observations"].update(trees=[], old_pin_matches=[])
            state = dict(entries=0, read_bytes=0, allocated=0, identities=set())
            pins = {row["path"]: row["sha256"] for row in selected["old_pins"]}
            for root in selected["roots"]:
                stage = "known_host_tree"
                _marker(parent, report)
                _scan_tree(root, guard, allowed_uids, report, state, pins)
            stage = "final_local_recheck"
            _marker(parent, report); _chain(parent, guard)
            require(_boot(guard) == observed_boot, "HOST_LOCAL_BOOT_CHANGED")
            require(set(report["observations"]["old_pin_matches"]) == set(pins), "HOST_LOCAL_OLD_PIN_MISSING")
            report["observations"].update(observed_unique_allocated_bytes=state["allocated"],
                observed_unique_inodes=state["entries"], file_bytes_read=state["read_bytes"],
                five_trees_complete=True, full_host_inventory_complete=False,
                historical_future_bytes=None, native_audit_peak_bytes=None,
                capture_bill_bytes=None, capture_admissible=None)
            guard()
        report.update(status="OBSERVED_PARTIAL", reason="LOCAL_FACTS_ONLY_LATER_ADMISSION_UNPROVEN")
    except Exception as error:
        report["reason"] = delivery.reason(error)
    report["stage"] = stage
    if window is not None:
        report["finished_monotonic_ns"] = window.monotonic()
        report["finished_boottime_ns"] = window.boottime()
    try:
        encode_report(report)
    except ValueError:
        report["observations"] = {"omitted_due_to_output_limit": True}
        report.update(status="LOCAL_PREFLIGHT_BLOCKED", reason="HOST_LOCAL_OUTPUT_LIMIT")
        encode_report(report)
    return report
