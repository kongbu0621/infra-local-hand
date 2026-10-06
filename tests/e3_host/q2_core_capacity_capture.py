"""One approved capacity observation; defaults to local-only verification.

Only --execute may consume lhqcap-20261006a. No business entry, retry, reset,
cleanup, new name or standalone post-capture replay entry is provided.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import posixpath
import re
import selectors
import shlex
import stat
import subprocess
import sys
import tarfile
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from e3_host import q2_core_capacity_reader as r
from e3_host import q2_core_obligation_inputs as obligations
from e3_host import q2_core_prior_attempt as prior
from e3_host import q2_core_delivery_contract as contract

# Reuse only existing local protection primitives. Never call its run/main,
# snapshot parser, remote reader, consumed entry or historical grammar checks.
_spec = importlib.util.spec_from_file_location("_capacity_local_protection",
    Path(__file__).with_name("q2_sshd_source_capture.py"))
local = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(local)

require, canonical, digest = r.require, r.canonical, r.digest
R = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
A = "1ba20d196facc82cf74aea88e7df3d4fe31e0584"
B = "LH-Q2-CORE-CAPACITY-OBSERVATION-CLOSURE-20261006-01"
C = "cd4dc50df1d62591548c54afa3e5405608aba20b"
ISSUED = "657b1bcd749cb4281b0193b2bc9430b0662faf98"
SESSION = r.SESSION
NAMES = {role: "." + SESSION + "." + suffix for role, suffix in
         (("marker", "consumed.json"), ("stdout", "stdout"), ("stderr", "stderr"), ("receipt", "receipt.json"))}
CAPS = dict(marker=4096, stdout=65536, stderr=65536, receipt=65536)
DOC_PINS = {
    "REQUIREMENTS.md": "d51bd38855359560bc4704645a07eb60c8efeebe3e6b8be847231976bd6b8d80",
    "ARCHITECTURE.md": "887b5b7328c3337d2b706c335728ff79199842e524e9ff20fea24ceff9f227e8",
    "IMPLEMENTATION_PLAN.md": "609cf344a35299a40842b41cfc911a9baf61a4ce35cbd793c61e7cd164e4eb36",
}
PLAN_ARCHIVE = (20164157, "078b4a5bc198caa42760c31d2a4f8d0be1dd3564090ea316c799bfe6d9e653f7")
PLAN_MEMBER = "root/q2-transfer-20260926a/plan.json"
MAPPING = {
    "state": ("/directories/state/path", "dirname"), "quota": ("/mounts/quota/path", "identity"),
    "install": ("/candidate/destination", "dirname"), "journal": ("/mounts/journal/path", "identity"),
    "evidence": ("/mounts/evidence/path", "identity"),
}
FOURTH_PINS = {
    "carrier-consumed.json": (3577, "ac0314d584ce7dfdbe5892f779cfbc01a702459fb31ab539b2752f70c07f7deb"),
    "stdout": (2852, "ff0f1b11037028b766c6bf8d4b6623f84241541f9e9240bf1f90efe3c9d6f7e9"),
    "stderr": (22, "e1c59576e732df777e6542b880a21994430f06f72ca54d9a0319507d1126aa75"),
    "capture-manifest.json": (1503, "44398704da222ff3d5200b53dfbc732c1ad23fa4b35bd4d75e4671c5b8d5b406"),
    "acceptance-receipt.json": (1117, "184439515c226a8b108b270522800174a7adb476191a606a66b7d451c25e601c"),
}
LOADER = ("import base64,hashlib,sys; r=base64.b64decode(sys.argv[1],validate=True); "
          "assert len(r)<=32768 and hashlib.sha256(r).hexdigest()==sys.argv[2]; "
          "exec(compile(r,'<fixed-capacity-reader>','exec'),{'__name__':'__main__'})")


def safe_reason(error):
    if type(error) in (r.ObservationError, local.CaptureError, contract.ContractError):
        code = str(error)
        if re.fullmatch(r"[A-Z0-9_]{1,160}", code):
            return code
    return "LOCAL_IO_OR_TRANSPORT"


def file_identity(info):
    return local.metadata(info) | {"atime_ns": info.st_atime_ns}


class Inputs:
    """Hold the seven exact saved sources, with stable fd/name identity."""
    def __init__(self):
        self.held = []
        self.bindings = {}

    def read(self, path, size, sha, role):
        path = os.fspath(path)
        parent = local.open_directory(str(Path(path).parent), os.geteuid())
        try:
            fd = os.open(Path(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC | os.O_NONBLOCK,
                         dir_fd=parent)
        finally:
            os.close(parent)
        before = file_identity(os.fstat(fd))
        self.held.append((path, fd, before))
        require(before["uid"] in (0, os.geteuid()) and not before["mode"] & 0o022, "INPUT_PROTECTION")
        raw, _ = local.stable_read(fd, size, lambda: None)
        require(len(raw) == size and digest(raw) == sha, "INPUT_PIN")
        self.bindings[role] = dict(bytes=size, sha256=sha)
        self.recheck()
        return raw

    def recheck(self, check=lambda: None):
        for path, fd, before in self.held:
            check()
            require(file_identity(os.fstat(fd)) == before and
                    file_identity(os.stat(path, follow_symlinks=False)) == before, "INPUT_DRIFT")
            check()

    def close(self):
        for _, fd, _ in self.held:
            os.close(fd)
        self.held.clear()


def plan_description(raw):
    require(len(raw) == 9814 and digest(raw) == r.PLAN_SHA, "PLAN_PIN")
    value = r.parse(raw, 9814)
    paths = {}
    for role, (pointer, transform) in MAPPING.items():
        source = value
        for key in pointer.split("/")[1:]:
            source = source[key]
        contract.absolute_path(source, "PLAN_PATH")
        path = posixpath.dirname(source) if transform == "dirname" else source
        r.path_value(path)
        paths[role] = path
    encoded = canonical(dict(schema="lhq-core-capacity-paths/v1", session=SESSION,
                             plan_sha256=r.PLAN_SHA, paths=paths))
    r.description(encoded)
    return encoded


def plan_from_archive(raw):
    require((len(raw), digest(raw)) == PLAN_ARCHIVE, "PLAN_ARCHIVE_PIN")
    found = None
    total = count = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r|gz") as archive:
        for member in archive:
            count += 1
            total += member.size
            require(count <= 20000 and total <= 536870912, "PLAN_ARCHIVE_LIMIT")
            if member.name == PLAN_MEMBER:
                require(found is None and member.isfile() and member.size == 9814, "PLAN_MEMBER")
                with archive.extractfile(member) as stream:
                    found = stream.read(9815)
    require(found is not None, "PLAN_MISSING")
    return plan_description(found)


def partitions(items):
    if not items:
        yield []
        return
    first, *rest = items
    for parts in partitions(rest):
        yield [[first], *parts]
        for index in range(len(parts)):
            yield [[first, *part] if i == index else part for i, part in enumerate(parts)]


def threshold(horizon, grouping):
    """Independent arithmetic only; never call any guest admission/helper."""
    require(set(grouping) == set(r.ROLES) and grouping["state"] == grouping["install"], "SYSTEM_POOL_SPLIT")
    pools = {key: {category: [0, 0] for category in ("snapshot", "delta", "quota", "prior", "05c")}
             for key in set(grouping.values())}
    roles = dict(grouping, system=grouping["state"])
    def charge(selected, category, size, count):
        r.integer(size); r.integer(count)
        for key in {roles[role] for role in selected}:
            pools[key][category][0] += size
            pools[key][category][1] += count
    for row in horizon["normalized_placement_rows"]:
        charge(row["pool_roles"], "snapshot", row["full_commitment"]["bytes"], row["full_commitment"]["inodes"])
    for row in horizon["delta_rows"]:
        charge([row["device_selector"].removesuffix("_parent")], "delta",
               row["commitment"]["bytes"], row["commitment"]["inodes"])
    for row in horizon["configured_quota_rows"]:
        charge(["quota"], "quota", row["hard_bytes"], row["inode_hard_limit"])
    # Exact 32 original pools: one install, one audit, three (state/journal/
    # capture/seven quota); plus the three original preparation reservations.
    vector = [(["install"], 67108864, 4096),
              (["state", "quota", "journal", "evidence"], 8388608, 512)]
    for _ in range(3):
        vector.extend([(["state", "quota", "journal", "evidence"], 8388608, 1536),
                       (["journal"], 1048576, 128), (["evidence"], 20971520, 384)])
        vector.extend([(["quota"], 1048576, 128)] * 7)
    require(len(vector) == 32 and sum(row[1] for row in vector) == 188743680 and
            sum(row[2] for row in vector) == 13440, "POOL_VECTOR")
    vector.append((["state"], 3 * 33554432, 3 * 1024))
    for selected, size, count in vector:
        charge(selected, "05c", size, count)
        charge(selected, "prior", 3 * size, 3 * count)
    return pools


def all_thresholds(horizon):
    result = []
    for parts in partitions(["system", "quota", "journal", "evidence"]):
        mapping = {role: index for index, group in enumerate(parts) for role in group}
        mapping["state"] = mapping["install"] = mapping.pop("system")
        pools = threshold(horizon, mapping)
        result.append(dict(groups=parts, pools=[pools[key] for key in sorted(pools)]))
    require(len(result) == 15, "GROUPING_COUNT")
    return result


def verify_threshold_anchors(horizon):
    separate = dict(state=0, install=0, quota=1, journal=2, evidence=3)
    pools = threshold(horizon, separate)
    actual = [tuple(sum(pair[index] for pair in pools[key].values()) for index in (0, 1)) for key in range(4)]
    require(actual == [(1535905792, 87281), (521142272, 57600), (299892736, 25472),
                       (553648128, 28160)], "DISJOINT_ANCHOR")
    shared = threshold(horizon, {role: 0 for role in r.ROLES})[0]
    require(tuple(sum(pair[index] for pair in shared.values()) for index in (0, 1)) ==
            (2172391424, 124017), "SHARED_ANCHOR")


def freeze_inputs(inputs, plan_archive, archives_dir):
    description = plan_from_archive(inputs.read(plan_archive, *PLAN_ARCHIVE, "plan_archive"))
    archives = {batch: inputs.read(Path(archives_dir) / name, size, sha, batch)
                for batch, name, size, sha in obligations.ARCHIVES}
    horizon = obligations.build_horizon(archives)
    verify_threshold_anchors(horizon)
    tables = all_thresholds(horizon)
    binding = dict(sources=inputs.bindings, plan_sha256=r.PLAN_SHA,
                   description_sha256=digest(description), horizon_sha256=digest(canonical(horizon)),
                   thresholds_sha256=digest(canonical(tables)), groupings=15)
    inputs.recheck()
    return description, horizon, binding


class Anchor(local.Anchor):
    def capacity(self):
        self.deadline.check()
        info = os.fstatvfs(self.fd)
        require(info.f_bavail * info.f_frsize >= 276824064 and info.f_favail >= 80, "HOST_CAPACITY")
        self.deadline.check()

    def bind_retained(self):
        self.retained = []
        seen = set()
        groups = [(prior.SESSION, prior.PINS), (prior.SECOND_SESSION, prior.SECOND_PINS),
                  ("lhqcore-20261005b", prior.THIRD_PINS), ("lhqcore-20261005c", FOURTH_PINS),
                  (prior.DIAGNOSTIC_SESSION, prior.DIAGNOSTIC_PINS)]
        for session, pins in groups:
            for suffix, (size, sha) in pins.items():
                self.deadline.check()
                name = "." + session + "." + suffix
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC | os.O_NONBLOCK,
                             dir_fd=self.fd)
                info = os.fstat(fd)
                self.held.append((name, fd, local.metadata(info)))
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                        stat.S_IMODE(info.st_mode) == 0o600 and info.st_uid == self.info["uid"] and
                        info.st_gid == self.info["gid"] and info.st_dev == self.info["dev"] and
                        (info.st_dev, info.st_ino) not in seen and (size is None or size == info.st_size), "PRIOR_FILE")
                seen.add((info.st_dev, info.st_ino))
                raw, _ = local.stable_read(fd, 65536, self.deadline.check)
                require(digest(raw) == sha, "PRIOR_PIN")
                self.retained.append(dict(basename=name, bytes=len(raw), sha256=sha))
            if session.startswith("lhqcore"):
                self.absent("." + session + ".remote-result.json")
        require(len(self.retained) == 24, "PRIOR_COUNT")
        self.recheck()


def make_argv(anchor, source, description):
    require(type(source) is bytes and 0 < len(source) <= 32768, "READER_SIZE")
    r.description(description)
    # Existing fixed SSH option list, with a wholly new remote data-only reader.
    argv = local.make_argv(anchor, b"# not executed")[:-1]
    command = ["exec", "/usr/bin/sudo", "-n", "--", "/usr/bin/env", "-i", "HOME=/root",
               "PATH=/usr/bin:/bin", "LANG=C", "LC_ALL=C", "/usr/bin/python3", "-I", "-B", "-c",
               LOADER, base64.b64encode(source).decode("ascii"), digest(source),
               base64.b64encode(description).decode("ascii"), digest(description)]
    return argv + [shlex.join(command)]


def validate_result(raw, source_sha, desc_raw):
    value = r.parse(raw, 65536)
    require(type(value) is dict and set(value) == {"schema", "session", "status", "source_sha256",
            "description_sha256", "euid", "limits", "start_ns", "end_ns", "rows"}, "RESULT_FIELDS")
    require(value["schema"] == r.SCHEMA and value["session"] == SESSION and
            value["status"] == "CURRENT_CAPACITY_OBSERVATION" and value["source_sha256"] == source_sha and
            value["description_sha256"] == digest(desc_raw) and type(value["euid"]) is int and value["euid"] == 0 and
            value["limits"] == r.LIMITS and all(type(v) is int for v in value["limits"].values()), "RESULT_BINDING")
    start, end = r.integer(value["start_ns"]), r.integer(value["end_ns"])
    require(0 <= end - start < 20_000_000_000, "RESULT_TIME")
    paths = r.description(desc_raw)["paths"]
    require(type(value["rows"]) is list and len(value["rows"]) == 5, "RESULT_ROWS")
    previous = start
    devices = {}
    directory_records = {}
    for role, row in zip(r.ROLES, value["rows"]):
        require(type(row) is dict and set(row) == {"role", "path", "directory", "filesystem", "statvfs",
                "available", "start_ns", "end_ns"} and row["role"] == role and row["path"] == paths[role], "RESULT_ROW")
        a, b = r.integer(row["start_ns"]), r.integer(row["end_ns"])
        require(previous <= a <= b <= end, "RESULT_SAMPLE_TIME")
        previous = b
        info = row["directory"]
        require(type(info) is dict and set(info) == set(r.IDENTITY), "RESULT_DIRECTORY")
        for v in info.values():
            r.integer(v)
        require(stat.S_ISDIR(info["mode"]) and stat.S_IMODE(info["mode"]) in (0o700, 0o755) and
                info["uid"] == info["gid"] == 0 and info["ino"] > 0, "RESULT_PROTECTION")
        fs = row["filesystem"]
        require(type(fs) is dict and set(fs) == {"uuid", "mount"} and type(fs["uuid"]) is str and
                re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", fs["uuid"]) and
                fs["uuid"] != "00000000-0000-0000-0000-000000000000", "RESULT_UUID")
        mount = fs["mount"]
        require(type(mount) is dict and set(mount) == {"mount_id", "device", "root", "path", "fstype", "source", "options"},
                "RESULT_MOUNT")
        r.integer(mount["mount_id"], 1); r.integer(mount["device"])
        require(mount["device"] == info["dev"] and mount["root"] == "/" and mount["fstype"] == "ext4", "RESULT_FILESYSTEM")
        for key in ("path", "source"):
            require(type(mount[key]) is str and 0 < len(mount[key]) <= 4096 and mount[key].isascii() and
                    not re.search(r"[\x00-\x20\\]", mount[key]), "RESULT_MOUNT_TEXT")
        require(mount["path"].startswith("/") and (mount["path"] == "/" or
                row["path"] == mount["path"] or row["path"].startswith(mount["path"].rstrip("/") + "/")), "RESULT_MOUNT_PATH")
        options = mount["options"]
        require(type(options) is list and 0 < len(options) <= 128 and all(type(x) is str and
                re.fullmatch(r"[A-Za-z0-9_=:./-]{1,256}", x) for x in options) and
                options == sorted(set(options)) and "rw" in options and "ro" not in options, "RESULT_MOUNT_OPTIONS")
        require(info["dev"] not in devices or devices[info["dev"]] == fs["uuid"], "RESULT_DEVICE_UUID")
        devices[info["dev"]] = fs["uuid"]
        require(row["path"] not in directory_records or directory_records[row["path"]] == (info, fs), "RESULT_PATH_IDENTITY")
        directory_records[row["path"]] = info, fs
        available = r.amounts(row["statvfs"])
        require(type(row["available"]) is dict and set(row["available"]) == {"bytes", "inodes"} and
                all(type(v) is int for v in row["available"].values()) and row["available"] == available, "RESULT_AVAILABLE")
    byrole = {row["role"]: (row["directory"]["dev"], row["filesystem"]["uuid"]) for row in value["rows"]}
    require(byrole["state"] == byrole["install"], "SYSTEM_POOL_SPLIT")
    return value


def compare(value, horizon, *, clock=time.monotonic_ns):
    start = clock()
    previous = start
    def check():
        nonlocal previous
        now = clock()
        require(previous <= now < start + 5_000_000_000, "COMPARISON_DEADLINE")
        previous = now
    check()
    grouping = {row["role"]: (row["directory"]["dev"], row["filesystem"]["uuid"]) for row in value["rows"]}
    pools = threshold(horizon, grouping)
    result = []
    for key, categories in pools.items():
        check()
        rows = [row for row in value["rows"] if grouping[row["role"]] == key]
        item = dict(roles=sorted(row["role"] for row in rows), device_sha256=digest(canonical(list(key))))
        for index, field in enumerate(("bytes", "inodes")):
            historical = sum(categories[category][index] for category in ("snapshot", "delta", "quota", "prior"))
            new = categories["05c"][index]
            available = min(row["available"][field] for row in rows)
            item[field] = dict(available=available, historical=historical, comparison_05c=new,
                               required=historical + new, deficit=max(0, historical + new - available))
        result.append(item)
    check()
    return dict(state="CONDITIONAL_05C_THRESHOLD_COMPARISON", pools=sorted(result, key=lambda x: x["roles"]),
                historical_placement="UNVERIFIED", current_quotas="UNVERIFIED", old_exit="UNKNOWN",
                current_mapping_assumed_for_frozen_contract=True, admission_proven=False)


class Capture:
    def __init__(self, anchor, deadline):
        self.anchor, self.deadline = anchor, deadline
        self.fds, self.infos, self.sizes, self.hashes, self.last_metadata = {}, {}, {}, {}, {}
        self.attempted, self.poisoned, self.max_allocated = set(), False, 0

    def check(self, final=False):
        self.deadline.remaining(60 if final else 55)
        require(local.observe_writer() == self.anchor.writer, "WRITER_DRIFT")
        info = os.fstat(self.anchor.fd)
        require(r.identity(info) == {k: self.anchor.info[k] for k in r.IDENTITY} and
                local.metadata(info) == local.metadata(os.stat(self.anchor.path, follow_symlinks=False)), "CAPTURE_PARENT")
        allocated = 0
        for role, fd in self.fds.items():
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600 and
                    info.st_uid == self.anchor.info["uid"] and info.st_gid == self.anchor.info["gid"] and
                    (info.st_dev, info.st_ino) == self.infos[role] and info.st_size == self.sizes[role] and
                    local.metadata(info) == self.last_metadata[role] and
                    local.metadata(os.stat(NAMES[role], dir_fd=self.anchor.fd, follow_symlinks=False)) == local.metadata(info),
                    "CAPTURE_DRIFT")
            allocated += info.st_blocks * 512
        self.max_allocated = max(allocated, self.max_allocated)
        require(allocated <= 4194304 and sum(self.sizes.values()) <= 4194304 and len(self.fds) <= 4, "CAPTURE_ALLOCATION")

    def create(self, role):
        self.check()
        require(not self.poisoned and role not in self.attempted and role in NAMES, "CAPTURE_REPLAY")
        self.attempted.add(role)
        try:
            fd = os.open(NAMES[role], os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NOATIME,
                         0o600, dir_fd=self.anchor.fd)
            self.fds[role] = fd
            info = os.fstat(fd)
            self.infos[role] = info.st_dev, info.st_ino
            self.sizes[role], self.hashes[role] = 0, hashlib.sha256()
            self.last_metadata[role] = local.metadata(info)
            self.check()
        except BaseException:
            self.poisoned = True
            raise

    def write(self, role, raw, *, final=False):
        self.check(final)
        require(role in self.fds and type(raw) is bytes and self.sizes[role] + len(raw) <= CAPS[role], "CAPTURE_LIMIT")
        offset = 0
        while offset < len(raw):
            self.check(final)
            count = os.write(self.fds[role], raw[offset:offset + 65536])
            require(count > 0, "CAPTURE_WRITE")
            self.hashes[role].update(raw[offset:offset + count])
            self.sizes[role] += count
            offset += count
            self.last_metadata[role] = local.metadata(os.fstat(self.fds[role]))
            self.check(final)

    def sync(self, final=False):
        for role, fd in self.fds.items():
            self.check(final)
            actual, offset = hashlib.sha256(), 0
            while offset < self.sizes[role]:
                self.check(final)
                raw = os.pread(fd, min(65536, self.sizes[role] - offset), offset)
                require(raw, "CAPTURE_SHORT_READ")
                actual.update(raw)
                offset += len(raw)
            require(actual.hexdigest() == self.hashes[role].hexdigest(), "CAPTURE_DIGEST")
        for fd in list(self.fds.values()) + [self.anchor.fd]:
            self.check(final)
            os.fsync(fd)
            self.check(final)

    def close(self):
        for fd in self.fds.values():
            os.close(fd)
        self.fds.clear()


def run_once(anchor, source, description, horizon, binding, deadline, *, popen=subprocess.Popen):
    cap = Capture(anchor, deadline)
    process, output, observed = None, bytearray(), None
    argv, env = binding["argv"], binding["environment"]
    status = dict(schema="lhq-core-capacity-receipt/v1", session=SESSION, state="FAILED", reason="NOT_STARTED",
        requests_attempted=0, marker_creation_attempted=False, marker_created=False, exit=None,
        stdout_eof=False, stderr_eof=False, observation_complete=False, remote_supervision_proven=False,
        remote_exit="UNKNOWN", exclusive_reservation_proven=False, old_commitments_refunded=False,
        R=R, A=A, B=B, C=C, D=binding["D"], reader_sha256=digest(source), description_sha256=digest(description),
        inputs_sha256=binding["inputs_sha256"], retained_sha256=binding["retained_sha256"],
        source_set_sha256=binding["source_set_sha256"],
        argv_environment_sha256=digest(canonical(dict(argv=argv, environment=env))), clock_origins_ns=deadline.origins,
        request_start_realtime_ns=time.time_ns())
    try:
        anchor.recheck()
        for name in NAMES.values():
            anchor.absent(name)
        anchor.capacity()
        cap.create("marker")
        cap.write("marker", canonical({key: status[key] for key in
            ("schema", "session", "R", "A", "B", "C", "D", "reader_sha256", "description_sha256", "inputs_sha256",
             "retained_sha256", "source_set_sha256", "argv_environment_sha256", "clock_origins_ns", "request_start_realtime_ns")}))
        cap.sync()
        for role in ("stdout", "stderr", "receipt"):
            cap.create(role)
        cap.sync()
        anchor.recheck(after_create=True)
        deadline.check()
        status["requests_attempted"] = 1
        process = popen(argv, executable=f"/proc/self/fd/{anchor.ssh}", pass_fds=(anchor.ssh,), stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=anchor.path, start_new_session=True)
        with selectors.DefaultSelector() as selector:
            for role, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, role)
            while selector.get_map():
                deadline.check()
                for event, _ in selector.select(min(0.1, deadline.remaining())):
                    deadline.check()
                    role = event.data
                    chunk = os.read(event.fileobj.fileno(), min(65536, CAPS[role] - cap.sizes[role] + 1))
                    if not chunk:
                        status[role + "_eof"] = True
                        selector.unregister(event.fileobj)
                        continue
                    remaining = CAPS[role] - cap.sizes[role]
                    cap.write(role, chunk[:remaining])
                    if role == "stdout":
                        output.extend(chunk[:remaining])
                    require(len(chunk) <= remaining, "STREAM_LIMIT_" + role.upper())
        status["exit"] = process.wait(timeout=deadline.remaining())
        require(status["exit"] == 0, "SSH_EXIT")
        observed = validate_result(bytes(output), digest(source), description)
        deadline.check()
        status.update(state="COMPLETE", reason="CURRENT_CAPACITY_OBSERVATION", observation_complete=True,
                      remote_exit="READER_REPORTED_COMPLETE_NOT_INDEPENDENTLY_SUPERVISED")
    except (Exception, KeyboardInterrupt) as error:
        status["reason"] = safe_reason(error)
    finally:
        status["marker_creation_attempted"] = "marker" in cap.attempted
        status["marker_created"] = True if "marker" in cap.fds else (None if "marker" in cap.attempted else False)
        if process is not None:
            try:
                if process.poll() is None:
                    process.kill()  # Only our direct local SSH child, never a group/guest.
                status["exit"] = process.wait(timeout=deadline.remaining(60))
            except (Exception, KeyboardInterrupt):
                status.update(state="UNKNOWN", observation_complete=False, remote_exit="UNKNOWN", reason="STOP_UNCONFIRMED")
            for stream in (process.stdout, process.stderr):
                stream.close()
        try:
            deadline.remaining(60)
            status["files"] = {role: dict(bytes=cap.sizes[role], sha256=cap.hashes[role].hexdigest())
                               for role in cap.sizes if role != "receipt"}
            status["observed_allocated_peak_before_receipt_bytes"] = cap.max_allocated
            status["host_deadline_met"] = True
            status["clock_final_ns"] = deadline.now()
            status["capture_final_realtime_ns"] = time.time_ns()
            if "receipt" in cap.fds:
                cap.write("receipt", canonical(status), final=True)
                cap.sync(final=True)
                status["files"]["receipt"] = dict(bytes=cap.sizes["receipt"], sha256=cap.hashes["receipt"].hexdigest())
        except (Exception, KeyboardInterrupt):
            status.update(state="UNKNOWN", observation_complete=False, reason="SEAL_INCOMPLETE", host_deadline_met=False)
        try:
            cap.close()
        except OSError:
            status.update(state="UNKNOWN", observation_complete=False, reason="LOCAL_CLOSE_INCOMPLETE")
    # One pure comparison after transport closure; never rewrite sealed captures.
    if status["state"] == "COMPLETE":
        try:
            status["comparison"] = compare(observed, horizon)
        except (Exception, KeyboardInterrupt) as error:
            status["comparison"] = dict(state="UNKNOWN", reason=safe_reason(error))
    return status


def freeze_repo(expected):
    require(re.fullmatch(r"[0-9a-f]{40}", expected), "D_FORMAT")
    repo = Path(__file__).resolve().parents[2]
    def git(*args):
        result = subprocess.run(["git", "-c", "maintenance.auto=false", "-c", "gc.auto=0", *args], cwd=repo,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        require(result.returncode == 0, "SOURCE_BASELINE")
        return result.stdout
    require(git("rev-parse", "HEAD").decode().strip() == expected and expected != C, "D_HEAD")
    git("diff", "--quiet", "HEAD")
    git("merge-base", "--is-ancestor", C, expected)
    for name, sha in DOC_PINS.items():
        require(digest(git("show", expected + ":docs/a2-execution/q2-core-capacity-observation/" + name)) == sha, "A_CHANGED")
    require(git("show", "bf8d391c3fdb24a5d4fc188b0ec9f2b36d9e5891:tests/e3_host/q2_sshd_source_capture.py") ==
            git("show", expected + ":tests/e3_host/q2_sshd_source_capture.py"), "LOCAL_PROTECTION_CHANGED")
    require(git("show", "bf8d391c3fdb24a5d4fc188b0ec9f2b36d9e5891:tests/e3_host/q2_sshd_source_reader.py") ==
            git("show", expected + ":tests/e3_host/q2_sshd_source_reader.py"), "LOCAL_PROTECTION_CHANGED")
    sources = {}
    names = ("q2_core_capacity_reader.py", "q2_core_capacity_capture.py", "q2_sshd_source_capture.py",
             "q2_sshd_source_reader.py", "q2_core_obligation_inputs.py", "q2_core_prior_attempt.py", "q2_core_delivery_contract.py")
    for name in names:
        path = Path(__file__).with_name(name)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC)
        try:
            raw, _ = local.stable_read(fd, 262144, lambda: None)
        finally:
            os.close(fd)
        require(raw == git("show", expected + ":tests/e3_host/" + name), "SOURCE_DRIFT")
        if name in names[4:]:
            require(raw == git("show", ISSUED + ":tests/e3_host/" + name), "HISTORICAL_CONTRACT_CHANGED")
        sources[name] = raw
    require(len(sources[names[0]]) <= 32768 and len(sources[names[1]]) <= 65536, "SOURCE_LIMIT")
    return sources


def preflight(anchor, source, description, commit, input_binding, source_binding):
    env = {key: os.environ[key] for key in ("HOME", "USER", "LOGNAME")}
    env.update(PATH="/usr/bin:/bin", LANG="C", LC_ALL="C")
    argv = make_argv(anchor.path, source, description)
    require(sum(len(x.encode()) + 1 for x in argv) + sum(len((k + "=" + v).encode()) + 1 for k, v in env.items())
            <= min(65536, os.sysconf("SC_ARG_MAX")), "ARGV_LIMIT")
    # -G checks option support locally using /dev/null, with all command/proxy hooks disabled.
    result = subprocess.run(argv[:1] + ["-G"] + argv[1:], executable=f"/proc/self/fd/{anchor.ssh}",
        pass_fds=(anchor.ssh,), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=min(5, anchor.deadline.remaining()), env=env)
    require(result.returncode == 0 and len(result.stdout) <= 65536 and len(result.stderr) <= 4096, "SSH_OPTIONS")
    anchor.recheck()
    for name in NAMES.values():
        anchor.absent(name)
    anchor.capacity()
    return dict(D=commit, argv=argv, environment=env, inputs_sha256=digest(canonical(input_binding)),
                retained_sha256=digest(canonical(anchor.retained)), source_set_sha256=digest(canonical(source_binding)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", required=True)
    parser.add_argument("--plan-archive", required=True)
    parser.add_argument("--archives-dir", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    inputs, anchor, entered = Inputs(), None, False
    try:
        sources = freeze_repo(args.expected_commit)
        description, horizon, input_binding = freeze_inputs(inputs, args.plan_archive, args.archives_dir)
        source_binding = {name: dict(bytes=len(raw), sha256=digest(raw)) for name, raw in sources.items()}
        # All O3 local management reads share these original clocks.
        deadline = local.Deadline()
        inputs.recheck(deadline.check)
        anchor = Anchor(args.anchor, deadline)
        anchor.bind_retained()
        source = sources["q2_core_capacity_reader.py"]
        binding = preflight(anchor, source, description, args.expected_commit, input_binding, source_binding)
        inputs.recheck(deadline.check)
        if args.execute:
            entered = True
            result = run_once(anchor, source, description, horizon, binding, deadline)
        else:
            result = dict(state="LOCAL_PREFLIGHT_PASSED", D=args.expected_commit, requests_attempted=0,
                          input_binding=input_binding, source_binding=source_binding)
        public = {key: result[key] for key in ("state", "reason", "D", "requests_attempted", "marker_created",
            "observation_complete", "remote_exit", "host_deadline_met", "request_start_realtime_ns", "capture_final_realtime_ns",
            "files", "comparison", "input_binding", "source_binding") if key in result}
        print(canonical(public).decode("ascii"), end="")
        return 0 if result["state"] in ("LOCAL_PREFLIGHT_PASSED", "COMPLETE") else 3
    except (Exception, KeyboardInterrupt) as error:
        print(canonical(dict(state="UNKNOWN" if entered else "BLOCKED", reason=safe_reason(error),
                             requests_attempted=None if entered else 0)).decode("ascii"), end="")
        return 3
    finally:
        inputs.close()
        if anchor is not None:
            anchor.close()


if __name__ == "__main__":
    sys.exit(main())
