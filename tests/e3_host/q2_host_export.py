"""Read-only, finite handoff from an explicitly selected existing Q1 guest.

This standalone stdlib tool neither imports installed code nor runs commands.
It exports selected current facts, not Q1 acceptance or a usable Q2 fixture.
Protected disk reads can block; the caller retains independent supervision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import PurePosixPath as P
import re
import socket
import stat
import sys

SCHEMA = "local-hand-q2-host-export/v1"
OUTPUT_LIMIT = 65536
READ_LIMIT = 256 * 1024 * 1024
HEX = r"[0-9a-f]{64}"
COMMIT = r"[0-9a-f]{40}"
UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
ROLES = ("python", "worker", "native", "systemd_run", "systemctl")
CONFIG_FILES = {"manifest.json": 32768, "runtime.json": 16384,
                "storage.json": 32768, "authority.json": 32768}
MISSING = ("q2_source_and_installed_wheel", "ordinary_broker_policy_and_empty_ledger",
           "ordinary_user_manager_and_delegation", "new_q2_root_allocations",
           "q2_query_management_controller_parents", "q2_operation_and_original_budgets",
           "q2_capacity_declaration", "q2_empty_output_and_declaration_directories",
           "original_supervisor_envelope_and_external_stop")


def require(ok, code):
    if not ok:
        raise ValueError(code)


def token(value, pattern):
    require(type(value) is str and re.fullmatch(pattern, value) is not None, "INVALID_TOKEN")
    return value


def path(value):
    token(value, r"/[A-Za-z0-9_./-]{1,1023}")
    require(str(P(value)) == value and not value.startswith("//") and ".." not in P(value).parts
            and value != "/", "NONCANONICAL_PATH")
    return value


def number(value, low=0):
    require(type(value) is int and low <= value < 2**63, "INVALID_INTEGER")
    return value


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), "CONFIG_FIELDS")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprint(info):
    return tuple(getattr(info, key) for key in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid",
        "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))


def file_identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, uid=info.st_uid, gid=info.st_gid, mode=info.st_mode)


class Reader:
    def __init__(self):
        self.used = 0

    def opened(self, name, *, directory=False, owner=0):
        path(name)
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOATIME
        fd = os.open("/", flags | os.O_DIRECTORY)
        try:
            parts = P(name).parts[1:]
            for index, part in enumerate(parts):
                isdir = directory or index + 1 < len(parts)
                child = os.open(part, flags | (os.O_DIRECTORY if isdir else 0), dir_fd=fd)
                os.close(fd); fd = child
                info = os.fstat(fd)
                expected_owner = owner if index + 1 == len(parts) else 0
                require(info.st_uid == expected_owner and not info.st_mode & 0o022
                        and (stat.S_ISDIR(info.st_mode) if isdir else stat.S_ISREG(info.st_mode)
                             and info.st_nlink == 1 and not info.st_mode & 0o6000), "UNPROTECTED_OBJECT")
            return fd
        except BaseException:
            os.close(fd)
            raise

    def read_fd(self, fd, limit):
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and not before.st_mode & 0o6000
                and before.st_size <= limit, "FILE_LIMIT_OR_TYPE")
        raw = bytearray()
        while len(raw) <= limit:
            require(self.used < READ_LIMIT, "AGGREGATE_READ_LIMIT")
            chunk = os.read(fd, min(65536, limit + 1 - len(raw), READ_LIMIT - self.used))
            if not chunk:
                break
            raw.extend(chunk); self.used += len(chunk)
        require(len(raw) <= limit and fingerprint(before) == fingerprint(os.fstat(fd)), "FILE_LIMIT_OR_CHANGED")
        return bytes(raw), before

    def read(self, name, limit):
        fd = self.opened(name)
        try:
            return self.read_fd(fd, limit)[0]
        finally:
            os.close(fd)

    def digest_fd(self, fd, limit):
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and not before.st_mode & 0o6000
                and before.st_size <= limit, "FILE_LIMIT_OR_TYPE")
        digest = hashlib.sha256(); length = 0; prefix = b""
        while length <= limit:
            require(self.used < READ_LIMIT, "AGGREGATE_READ_LIMIT")
            chunk = os.read(fd, min(65536, limit + 1 - length, READ_LIMIT - self.used))
            if not chunk: break
            if not prefix: prefix = chunk[:4]
            digest.update(chunk); length += len(chunk); self.used += len(chunk)
        require(length <= limit and length == before.st_size
                and fingerprint(before) == fingerprint(os.fstat(fd)), "FILE_LIMIT_OR_CHANGED")
        return digest.hexdigest(), prefix, length, before

    def kernel(self, name, limit=4096):
        # Only fixed caller-selected proc/sysfs paths, never arbitrary JSON paths.
        fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            return self.read_fd(fd, limit)[0]
        finally:
            os.close(fd)

    def directory(self, name, owner=0):
        fd = self.opened(name, directory=True, owner=owner)
        try:
            info = os.fstat(fd)
            return file_identity(info)
        finally:
            os.close(fd)


def document(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "DUPLICATE_KEY"); value[key] = item
        return value
    def reject(_):
        raise ValueError("JSON_NUMBER")
    value = json.loads(raw, object_pairs_hook=pairs, parse_float=reject, parse_constant=reject)
    pending = [(value, 0)]; count = 0
    while pending:
        item, depth = pending.pop(); count += 1
        require(depth <= 12 and count <= 4096, "JSON_COMPLEXITY")
        if type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is int:
            number(item)
        else:
            require(type(item) in (str, bool) or item is None, "JSON_VALUE")
    require(type(value) is dict, "CONFIG_OBJECT")
    return value


def host(reader, expected):
    require(sys.platform.startswith("linux"), "LINUX_REQUIRED")
    require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 0, "ROOT_REQUIRED")
    token(expected, r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}")
    require(socket.gethostname() == expected, "HOSTNAME_MISMATCH")
    require(reader.kernel("/proc/1/comm").strip() == b"systemd", "SYSTEMD_REQUIRED")
    vendor = reader.kernel("/sys/class/dmi/id/sys_vendor").decode("ascii").strip()
    product = reader.kernel("/sys/class/dmi/id/product_name").decode("ascii").strip()
    require(len(vendor) <= 128 and len(product) <= 128 and
            (vendor in ("QEMU", "KVM") or product == "KVM"), "ISOLATED_GUEST_HINT_REQUIRED")
    boot = token(reader.kernel("/proc/sys/kernel/random/boot_id").decode("ascii").strip(), UUID)
    kernel = reader.kernel("/proc/sys/kernel/osrelease").decode("ascii").strip()
    require(len(kernel) <= 128, "KERNEL_TEXT_LIMIT")
    ns = os.stat("/proc/self/ns/user"); init = os.stat("/proc/1/ns/user")
    require((ns.st_dev, ns.st_ino) == (init.st_dev, init.st_ino), "INITIAL_USER_NAMESPACE_REQUIRED")
    return dict(hostname=expected, boot_id=boot, kernel=kernel, dmi_vendor=vendor, dmi_product=product,
                guest_identity="MATCHING_DECLARED_GUEST_HINTS_ONLY", initial_userns=dict(device=ns.st_dev, inode=ns.st_ino))


def config(reader, directory, expected_revision=None):
    anchor = reader.read(directory + "/SHA256SUMS", 65536)
    rows = anchor.decode("ascii").splitlines()
    require(1 <= len(rows) <= 64, "CONFIG_SEAL_COUNT")
    seals = {}
    for row in rows:
        digest, name = row.split(maxsplit=1)
        token(digest, HEX); path(name)
        require(name not in seals or seals[name] == digest, "CONFLICTING_CONFIG_SEAL")
        seals[name] = digest
    raw = {name: reader.read(directory + "/" + name, limit) for name, limit in CONFIG_FILES.items()}
    for name in ("manifest.json", "runtime.json", "storage.json"):
        require(seals.get(directory + "/" + name) == sha(raw[name]), "CONFIG_DIGEST_MISMATCH")
    values = {name: document(data) for name, data in raw.items()}
    manifest = values["manifest.json"]; runtime = values["runtime.json"]
    keys(manifest, ("schema", "authority_digest", "installation_digest", "source_commit", "boot_id", "epoch",
                   "query_uid", "query_euid", "abi", "cgroup_parent", "max_query_ns", "slots"))
    require(manifest["schema"] == "local-hand-quota-q1-manifest/v1", "Q1_MANIFEST_SCHEMA")
    require(runtime.get("schema") == "local-hand-quota-runtime/v1", "Q1_RUNTIME_SCHEMA")
    token(manifest["source_commit"], COMMIT); token(manifest["boot_id"], UUID)
    require(expected_revision is None or manifest["source_commit"] == expected_revision, "REVISION_CONFIG_MISMATCH")
    require(manifest["authority_digest"] == sha(raw["authority.json"]), "Q1_AUTHORITY_BINDING")
    require(runtime.get("manifest_path") == directory + "/manifest.json"
            and runtime.get("manifest_digest") == sha(raw["manifest.json"]), "Q1_MANIFEST_BINDING")
    install = {}
    for role in ROLES:
        install[role + "_path"] = path(runtime[role + "_path"])
        install[role + "_sha256"] = token(runtime[role + "_sha256"], HEX)
    packages = runtime["package_files"]
    keys(packages, ("admission.py", "protected_inputs.py", "supervision.py"))
    for digest in packages.values(): token(digest, HEX)
    install["package_files"] = packages
    require(sha(json.dumps(install, sort_keys=True, separators=(",", ":")).encode()) == manifest["installation_digest"],
            "Q1_INSTALLATION_BINDING")
    query_slice = token(runtime["query_slice"], r"lhq[a-z0-9]{1,40}\.slice")
    require(manifest["cgroup_parent"] == "/" + query_slice, "Q1_PARENT_BINDING")
    for key in ("cgroup_parent_device", "cgroup_parent_inode", "initial_userns_device", "initial_userns_inode"):
        number(runtime[key])
    require(type(manifest["slots"]) is list and 1 <= len(manifest["slots"]) <= 32, "Q1_SLOT_COUNT")
    for slot in manifest["slots"]:
        keys(slot, ("ref", "generation", "path", "filesystem", "filesystem_uuid", "root", "project_id", "xflags", "hard_bytes"))
        token(slot["ref"], r"[a-z0-9][a-z0-9_.-]{0,63}"); token(slot["generation"], r"[0-9a-f]{32}")
        path(slot["path"]); token(slot["filesystem"], r"ext4|xfs"); token(slot["filesystem_uuid"], UUID)
        keys(slot["root"], ("device", "inode", "uid", "gid", "mode"))
        for item in slot["root"].values(): number(item)
        number(slot["root"]["uid"], 1)
        require(slot["root"]["mode"] == stat.S_IFDIR | 0o700, "Q1_SLOT_MODE")
        for key in ("project_id", "xflags", "hard_bytes"): number(slot[key], 1)
    storage = values["storage.json"]
    keys(storage, ("journal", "evidence"))
    for item in storage.values():
        require(type(item) is dict and {"path", "device", "inode", "owner_uid"} <= set(item), "Q1_STORAGE_FIELDS")
        path(item["path"])
        for key in ("device", "inode", "owner_uid"): number(item[key])
    summary = dict(status="Q1_CONFIG_BYTES_LINKED_ONLY", source_commit=manifest["source_commit"],
        boot_id=manifest["boot_id"], seal_sha256=sha(anchor), files={name: sha(data) for name, data in raw.items()},
        independent_authority_proven=False, q2_reusable_allocation=False)
    return values, summary


def mounts(raw):
    result = []
    lines = raw.decode("utf-8").splitlines(); require(len(lines) <= 4096, "MOUNT_COUNT")
    def unescape(value):
        return re.sub(r"\\(040|011|012|134)", lambda m: chr(int(m[1], 8)), value)
    for line in lines:
        left, right = line.split(" - ", 1); a = left.split(); b = right.split()
        require(len(a) >= 6 and len(b) >= 3, "MOUNT_FORMAT")
        result.append(dict(mount_id=int(a[0]), device=a[2], mountpoint=unescape(a[4]),
                           filesystem=b[0], options=a[5], super_options=b[2]))
    return result


def selected_mount(entries, name, device):
    choices = [item for item in entries if name == item["mountpoint"] or
               name.startswith(item["mountpoint"].rstrip("/") + "/")]
    require(bool(choices), "MOUNT_MISSING")
    longest = max(len(item["mountpoint"]) for item in choices)
    choices = [item for item in choices if len(item["mountpoint"]) == longest]
    require(len(choices) == 1, "MOUNT_AMBIGUOUS")
    result = choices[0]
    require(result["device"] == str(os.major(device)) + ":" + str(os.minor(device)), "MOUNT_DEVICE_MISMATCH")
    return result


def root_fact(reader, name, expected, entries):
    actual = reader.directory(name, expected["uid"])
    require(all(actual[key] == expected[key] for key in expected), "DIRECTORY_IDENTITY_CHANGED")
    return dict(path=name, actual=actual, mount=selected_mount(entries, name, actual["device"]))


def program(reader, runtime, role):
    name = runtime[role + "_path"]; fd = reader.opened(name)
    try:
        digest, prefix, length, info = reader.digest_fd(fd, 512 * 1024 if role == "worker" else 64 * 1024 * 1024)
        require(digest == runtime[role + "_sha256"], "PROGRAM_DIGEST_CHANGED")
        if role != "worker":
            require(prefix == b"\x7fELF" and info.st_mode & 0o111, "PROGRAM_NOT_EXECUTABLE_ELF")
        return dict(path=name, sha256=digest, size=length, identity=file_identity(info), executed=False)
    finally:
        os.close(fd)


def source_head(reader, source, declared):
    raw = reader.read(source + "/.git/HEAD", 256)
    head = raw.decode("ascii").strip()
    token(head, COMMIT); require(head == declared, "SOURCE_HEAD_MISMATCH")
    return dict(declared_commit=declared, detached_head=head, head_sha256=sha(raw),
                source_bytes_verified=False, clean_tree_verified=False)


def accounts(reader, uids):
    raw = reader.read("/etc/passwd", 1024 * 1024); selected = []
    for line in raw.decode("utf-8").splitlines():
        fields = line.split(":"); require(len(fields) == 7, "PASSWD_FORMAT")
        uid = int(fields[2]); gid = int(fields[3])
        if uid in uids:
            selected.append(dict(name=fields[0], uid=uid, gid=gid))
    require(len(selected) == len(uids) and {item["uid"] for item in selected} == uids, "ACCOUNT_MISSING_OR_ALIAS")
    return selected


def cgroup(reader, runtime):
    name = "/sys/fs/cgroup/" + runtime["query_slice"]
    actual = reader.directory(name)
    require((actual["device"], actual["inode"]) ==
            (runtime["cgroup_parent_device"], runtime["cgroup_parent_inode"]), "Q1_PARENT_CHANGED")
    events = reader.kernel(name + "/cgroup.events").decode("ascii").splitlines()
    values = dict(line.split() for line in events)
    require(set(values) <= {"populated", "frozen"} and values.get("populated") in ("0", "1"), "CGROUP_EVENTS")
    return dict(path=name, identity=actual, events=values, q2_parent_admitted=False)


def reason(error):
    value = str(error)
    return value if isinstance(error, ValueError) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else type(error).__name__


def report():
    return dict(schema=SCHEMA, status="BLOCKED", scope="READ_ONLY_SELECTED_Q1_HOST_HANDOFF",
        source_config_status="NOT_READ", checks=[], q2_input_groups={key: "NOT_DELIVERED" for key in MISSING},
        q1_history_reassessed=False, q2_accepted=False, q3_accepted=False, production_supported=False,
        complete_q1_domain_inventory=False,
        quota_observed=False, current_capacity_is_new_budget=False, fixture_generated=False,
        independent_supervision_required=True)


def export(root, revision, expected_hostname, reader=None):
    result = report(); reader = Reader() if reader is None else reader
    def probe(name, action):
        try:
            value = action(); result["checks"].append(dict(check=name, status="OBSERVED", facts=value)); return value
        except Exception as error:
            result["checks"].append(dict(check=name, status="BLOCKED", reason=reason(error))); return None
    path(root); token(revision, COMMIT)
    machine = probe("declared_guest", lambda: host(reader, expected_hostname))
    if machine is None:
        return result
    if probe("q1_installation_root", lambda: reader.directory(root)) is None:
        return result
    entries = probe("mount_table", lambda: mounts(reader.kernel("/proc/self/mountinfo", 1024 * 1024)))
    # The full mount table is an internal selector, never an exported host inventory.
    if entries is not None: result["checks"][-1]["facts"] = dict(entries_read=len(entries))
    uids = set(); linked = 0
    for label, base, expected in (("original", root, None), ("revision", root + "/revisions/" + revision, revision)):
        loaded = probe(label + "_config", lambda base=base, expected=expected: config(reader, base + "/config", expected))
        if loaded is None: continue
        values, summary = loaded; result["checks"][-1]["facts"] = summary; linked += 1
        manifest = values["manifest.json"]; runtime = values["runtime.json"]
        probe(label + "_current_boot", lambda manifest=manifest: require(manifest["boot_id"] == machine["boot_id"], "Q1_BOOT_CHANGED"))
        probe(label + "_source_head", lambda base=base, manifest=manifest: source_head(reader, base + "/source", manifest["source_commit"]))
        for role in ROLES:
            probe(label + "_program_" + role, lambda role=role, runtime=runtime: program(reader, runtime, role))
        probe(label + "_query_parent", lambda runtime=runtime: cgroup(reader, runtime))
        for index, slot in enumerate(manifest["slots"]):
            uids.add(slot["root"]["uid"])
            if entries is not None:
                probe(label + "_retained_slot_" + str(index), lambda slot=slot: dict(
                    **root_fact(reader, slot["path"], slot["root"], entries),
                    declared_project=slot["project_id"], declared_filesystem_uuid=slot["filesystem_uuid"],
                    declared_hard_bytes=slot["hard_bytes"], quota_rechecked=False, q2_reusable=False))
        for role, item in values["storage.json"].items():
            if entries is not None:
                probe(label + "_storage_" + role, lambda item=item: root_fact(reader, item["path"],
                    dict(device=item["device"], inode=item["inode"], uid=item["owner_uid"]), entries))
    if uids: probe("selected_existing_accounts", lambda: accounts(reader, uids))
    result["source_config_status"] = "Q1_EVIDENCE_ONLY" if linked else "NOT_LINKED"
    result["status"] = "EXPORTED" if linked == 2 and all(row["status"] == "OBSERVED" for row in result["checks"]) else "PARTIAL"
    result["read_bytes"] = reader.used
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--q1-root"); parser.add_argument("--q1-revision"); parser.add_argument("--expected-hostname")
    args = parser.parse_args(argv)
    result = report()
    try:
        require(all((args.q1_root, args.q1_revision, args.expected_hostname)), "EXPLICIT_PRIVATE_INPUTS_REQUIRED")
        require(sys.flags.isolated and sys.dont_write_bytecode, "ISOLATED_PYTHON_REQUIRED")
        result = export(args.q1_root, args.q1_revision, args.expected_hostname)
        raw = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        require(len(raw.encode()) + 1 <= OUTPUT_LIMIT, "OUTPUT_LIMIT")
    except Exception as error:
        result = report(); result["reason"] = reason(error)
        raw = json.dumps(result, sort_keys=True, separators=(",", ":"))
    print(raw)
    return 0 if result["status"] == "EXPORTED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
