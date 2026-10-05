"""Single, separately approved sshd snapshot; never a core carrier entry.

Default CLI is local-only preflight. --execute is the sole consuming operation.
No recovery constructor, retry, cleanup, or alternate destination exists.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import stat
import subprocess
import sys
import time

_spec = importlib.util.spec_from_file_location("_sshd_snapshot_reader", Path(__file__).with_name("q2_sshd_source_reader.py"))
reader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reader)
require = reader.require
CaptureError = reader.CaptureError
canonical = reader.canonical
metadata = reader.metadata

R = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
A = "f2eb31deb3c52d69ccd2079fb7d88608d1a25a62"
C = "b346cbd44dd4f376d4386f72d7029b1311788229"
SESSION = reader.SESSION
PREFIX = "." + SESSION
NAMES = {"marker": PREFIX + ".consumed.json", "stdout": PREFIX + ".stdout",
         "stderr": PREFIX + ".stderr", "receipt": PREFIX + ".receipt.json"}
CAPS = {"marker": 4096, "stdout": 2097152, "stderr": 65536, "receipt": 65536}
PINS = {
    "ssh.sh": (0o700, "aed91e80483d4df103f95c1d4cd5bf9bd18720f4dc51720702c329c937f93c63"),
    "start.sh": (0o700, "1acc8c4cb09bc5b14c32adc35e87d8500098cbf3968d53f406269e96df30f96a"),
    "user-data": (0o600, "5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523"),
    "id_ed25519.pub": (0o600, "e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c"),
    "known_hosts": (0o644, "d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd"),
}
DOC_PINS = {
    "REQUIREMENTS.md": "e9fb702b74b86381d5e8ed47722d7203528444a137b58e86a7a192d3a1e58e08",
    "ARCHITECTURE.md": "62b2a95421364055fa65b2899087ab116632190a5be378399501cbf88b629962",
    "IMPLEMENTATION_PLAN.md": "8c280c33d7643dbc5daf9ed00d3058b1d471bc76685db9b18a7a5d2f9328ecc5",
}
LOADER = ("import base64,hashlib,sys; r=base64.b64decode(sys.argv[1],validate=True); "
          "assert len(r)<=32768 and hashlib.sha256(r).hexdigest()==sys.argv[2]; "
          "exec(compile(r,'<fixed-sshd-reader>','exec'),{'__name__':'__main__'})")
PARSERS = ("71d6f43d98a8b71763e7925c43b2becaec184e11", "46b08d9640ca19505fa02aa89d5d71d298536489")
# Only the two original grammar functions and their raising helper are compiled.
# The digest/canonical helpers operate solely on validator-produced bytes/data.
PARSER_WORKER = r'''
import ast,base64,hashlib,json,re,sys
p=json.load(sys.stdin)
tree=ast.parse(p["source"])
names={"_admit_sshd_source","_admit_text","_require"}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
assert len(nodes)==3
class DispatchError(RuntimeError): pass
ns={"DispatchError":DispatchError,"re":re,"_sha":lambda raw:hashlib.sha256(raw).hexdigest(),
    "canonical":lambda value:json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode("ascii")}
exec(compile(ast.Module(body=nodes,type_ignores=[]),"<pinned-grammar>","exec"),ns)
raws={path:base64.b64decode(value,validate=True) for path,value in p["files"]}
assert len(raws)<=65 and sum(map(len,raws.values()))<=1048576
try:
    ns["_admit_sshd_source"](raws)
    result={"state":"ACCEPTED","code":"SOURCE_GRAMMAR_ACCEPTED"}
except DispatchError as error:
    code=str(error)
    assert len(code)<=512 and re.fullmatch("[A-Z0-9_]+",code)
    result={"state":"REJECTED","code":code}
print(json.dumps(result,sort_keys=True))
'''


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class Deadline:
    def __init__(self, clock=time.clock_gettime_ns):
        require(hasattr(time, "CLOCK_BOOTTIME"), "CLOCK_UNSUPPORTED")
        self.clock = clock
        self.origins = self.now()
        self.previous = self.origins

    def now(self):
        return (self.clock(time.CLOCK_BOOTTIME), self.clock(time.CLOCK_MONOTONIC))

    def remaining(self, limit=55):
        now = self.now()
        require(all(type(v) is int and p <= v for p, v in zip(self.previous, now)), "CLOCK_DRIFT")
        self.previous = now
        remaining = min(limit - (n - o) / 1e9 for n, o in zip(now, self.origins))
        require(remaining > 0, "DEADLINE")
        return remaining

    def check(self):
        self.remaining()


def stable_read(fd, limit, check):
    check()
    before = os.fstat(fd)
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= limit, "LOCAL_FILE")
    chunks = bytearray()
    while True:
        check()
        part = os.read(fd, min(65536, limit + 1 - len(chunks)))
        check()
        if not part:
            break
        chunks.extend(part)
        require(len(chunks) <= limit, "LOCAL_FILE_LIMIT")
    require(len(chunks) == before.st_size and metadata(before) == metadata(os.fstat(fd)), "LOCAL_FILE_DRIFT")
    return bytes(chunks), metadata(before)


def open_directory(path, owner):
    """Metadata-only O_PATH traversal; does not read root-owned directory data."""
    require(os.path.isabs(path) and os.path.normpath(path) == path, "LOCAL_PATH")
    fd = os.open("/", os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        for component in Path(path).parts[1:]:
            new = os.open(component, os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
            info = os.fstat(fd)
            require(info.st_uid in (0, owner) and not info.st_mode & 0o022, "LOCAL_PARENT")
        return fd
    except BaseException:
        os.close(fd)
        raise


def bound_executable(path):
    parent = open_directory(str(Path(path).parent), 0)
    try:
        fd = os.open(Path(path).name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
    finally:
        os.close(parent)
    info = os.fstat(fd)
    try:
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022
                and info.st_mode & 0o111, "LOCAL_EXECUTABLE")
        return fd, metadata(info)
    except BaseException:
        os.close(fd)
        raise


def observe_writer():
    values = {}
    for name, cap in (("status", 65536), ("stat", 16384)):
        fd = os.open("/proc/self/" + name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC)
        try:
            raw = os.read(fd, cap + 1)
            require(len(raw) <= cap, "WRITER_LIMIT")
            values[name] = raw.decode("ascii")
        finally:
            os.close(fd)
    ids = {}
    for line in values["status"].splitlines():
        key, _, value = line.partition(":")
        if key in ("Uid", "Gid", "Groups"):
            require(key not in ids, "WRITER_FIELDS")
            ids[key] = [int(v) for v in value.split()]
    require(set(ids) == {"Uid", "Gid", "Groups"} and len(ids["Uid"]) == len(ids["Gid"]) == 4,
            "WRITER_FIELDS")
    tail = values["stat"].rpartition(") ")[2].split()
    require(len(tail) >= 20, "WRITER_FIELDS")
    namespaces = {}
    for name in ("user", "pid"):
        # The same two explicit self namespace handles used by the existing
        # writer observer; no namespace creation or guest namespace inspection.
        fd = os.open("/proc/self/ns/" + name, os.O_RDONLY | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            namespaces[name] = {"dev": info.st_dev, "ino": info.st_ino}
        finally:
            os.close(fd)
    return dict(pid=os.getpid(), starttime=int(tail[19]), namespaces=namespaces, **ids)


def known_endpoint(raw):
    target = b"[127.0.0.1]:22221"
    for line in raw.splitlines():
        if not line.strip() or line.startswith(b"#"):
            continue
        words = line.split()
        require(len(words) == 3 and not words[0].startswith(b"@"), "KNOWN_HOST_FORMAT")
        host = words[0]
        if host.startswith(b"|1|"):
            parts = host.split(b"|")
            require(len(parts) == 4, "KNOWN_HOST_FORMAT")
            salt, expected = (base64.b64decode(x, validate=True) for x in parts[2:])
            if hmac.compare_digest(hmac.new(salt, target, hashlib.sha1).digest(), expected):
                return
        elif target in host.split(b","):
            return
    raise CaptureError("KNOWN_HOST_ENDPOINT")


def make_argv(anchor, source):
    require(type(source) is bytes and len(source) + len(LOADER.encode()) <= 32768, "READER_SIZE")
    command = ["exec", "/usr/bin/sudo", "-n", "--", "/usr/bin/env", "-i", "HOME=/root",
               "PATH=/usr/bin:/bin", "LANG=C", "LC_ALL=C", "/usr/bin/python3", "-I", "-B", "-c",
               LOADER, base64.b64encode(source).decode("ascii"), digest(source)]
    options = ["IdentitiesOnly=yes", "IdentityAgent=none", "BatchMode=yes", "StrictHostKeyChecking=yes",
               "UpdateHostKeys=no", "CheckHostIP=no", "GlobalKnownHostsFile=/dev/null", "VerifyHostKeyDNS=no",
               "PreferredAuthentications=publickey", "PubkeyAuthentication=yes", "PasswordAuthentication=no",
               "KbdInteractiveAuthentication=no", "GSSAPIAuthentication=no", "HostbasedAuthentication=no",
               "ConnectionAttempts=1", "ConnectTimeout=10", "ControlMaster=no", "ControlPath=none",
               "ControlPersist=no", "ProxyCommand=none", "ProxyJump=none", "ClearAllForwardings=yes",
               "ForwardAgent=no", "ForwardX11=no", "RequestTTY=no", "PermitLocalCommand=no",
               "CanonicalizeHostname=no", "NumberOfPasswordPrompts=0", "AddKeysToAgent=no"]
    argv = ["/usr/bin/ssh", "-F", "/dev/null", "-T", "-4", "-i", anchor + "/id_ed25519", "-p", "22221"]
    for option in options + ["UserKnownHostsFile=" + anchor + "/known_hosts"]:
        argv.extend(["-o", option])
    return argv + ["q1admin@127.0.0.1", shlex.join(command)]


class Anchor:
    def __init__(self, path, deadline):
        self.path, self.deadline = path, deadline
        self.fd = None
        self.held = []
        self.executables = []
        self.writer = observe_writer()
        self.raw = {}
        try:
            deadline.check()
            require(all(x == os.geteuid() for x in self.writer["Uid"]) and
                    all(x == os.getegid() for x in self.writer["Gid"]), "WRITER_IDS")
            parent = open_directory(path, os.geteuid())
            try:
                self.fd = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOATIME,
                                  dir_fd=parent)
                require(metadata(os.fstat(parent)) == metadata(os.fstat(self.fd)), "ANCHOR_DRIFT")
            finally:
                os.close(parent)
            self.info = metadata(os.fstat(self.fd))
            require(stat.S_IMODE(self.info["mode"]) == 0o700 and self.info["uid"] == os.geteuid()
                    and self.info["gid"] == os.getegid(), "ANCHOR_PROTECTION")
            for name, (mode, sha) in PINS.items():
                fd, info = self.file(name, mode)
                raw, _ = stable_read(fd, 65536, deadline.check)
                require(digest(raw) == sha, "MANAGEMENT_PIN")
                self.raw[name] = raw
            match = re.search(rb"^q1_vm=(/[^\n]+)$", self.raw["ssh.sh"], re.M)
            require(match is not None and match[1].decode("ascii") == path, "ANCHOR_RELATION")
            known_endpoint(self.raw["known_hosts"])
            self.absent("id_ed25519-cert.pub")
            private, _ = self.file("id_ed25519", 0o600, maximum=16384)
            keygen = self.executable("/usr/bin/ssh-keygen")
            self.ssh = self.executable("/usr/bin/ssh")
            result = subprocess.run(["/usr/bin/ssh-keygen", "-y", "-f", f"/proc/self/fd/{private}"],
                executable=f"/proc/self/fd/{keygen}", pass_fds=(private, keygen), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=min(5, deadline.remaining()),
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}, check=False)
            require(result.returncode == 0 and len(result.stderr) <= 4096 and
                    digest(result.stdout) == PINS["id_ed25519.pub"][1], "PRIVATE_PUBLIC_BINDING")
            self.recheck()
        except BaseException:
            self.close()
            raise

    def absent(self, name):
        try:
            os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise CaptureError("OBJECT_EXISTS")

    def file(self, name, mode, maximum=65536):
        self.deadline.check()
        before = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                stat.S_IMODE(before.st_mode) == mode and before.st_uid == self.info["uid"] and
                before.st_gid == self.info["gid"] and 0 < before.st_size <= maximum, "MANAGEMENT_FILE")
        fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NOATIME | os.O_NONBLOCK,
                     dir_fd=self.fd)
        self.held.append((name, fd, metadata(before)))
        require(metadata(os.fstat(fd)) == metadata(before), "MANAGEMENT_DRIFT")
        return fd, metadata(before)

    def executable(self, path):
        fd, info = bound_executable(path)
        self.executables.append((path, fd, info))
        return fd

    def recheck(self, *, after_create=False):
        self.deadline.check()
        require(observe_writer() == self.writer, "WRITER_DRIFT")
        current = metadata(os.fstat(self.fd))
        keys = ("dev", "ino", "mode", "uid", "gid", "nlink") if after_create else reader.META
        require(all(current[k] == self.info[k] for k in keys) and
                metadata(os.stat(self.path, follow_symlinks=False)) == current, "ANCHOR_DRIFT")
        self.absent("id_ed25519-cert.pub")
        for name, fd, before in self.held:
            require(metadata(os.fstat(fd)) == before and
                    metadata(os.stat(name, dir_fd=self.fd, follow_symlinks=False)) == before, "MANAGEMENT_DRIFT")
        for path, fd, before in self.executables:
            require(metadata(os.fstat(fd)) == before and metadata(os.lstat(path)) == before, "EXECUTABLE_DRIFT")

    def capacity(self):
        self.deadline.check()
        info = os.fstatvfs(self.fd)
        require(info.f_bavail * info.f_frsize >= 205520896 and info.f_favail >= 56, "HOST_CAPACITY")
        self.deadline.check()

    def close(self):
        for _, fd, _ in self.held + self.executables:
            os.close(fd)
        self.held.clear()
        self.executables.clear()
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


class Capture:
    def __init__(self, anchor, deadline):
        self.anchor, self.deadline = anchor, deadline
        self.fds, self.infos, self.sizes, self.hashes = {}, {}, {}, {}
        self.last_metadata = {}
        self.attempted = set()
        self.poisoned = False
        self.max_allocated = 0

    def check(self, final=False):
        self.deadline.remaining(60 if final else 55)
        require(observe_writer() == self.anchor.writer, "WRITER_DRIFT")
        info = os.fstat(self.anchor.fd)
        require((info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid) ==
                tuple(self.anchor.info[k] for k in ("dev", "ino", "mode", "uid", "gid")), "CAPTURE_PARENT")
        named_parent = os.stat(self.anchor.path, follow_symlinks=False)
        require(metadata(info) == metadata(named_parent), "CAPTURE_PARENT")
        allocated = 0
        for role, fd in self.fds.items():
            info = os.fstat(fd)
            before = self.infos[role]
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                    stat.S_IMODE(info.st_mode) == 0o600 and info.st_uid == self.anchor.info["uid"] and
                    info.st_gid == self.anchor.info["gid"] and
                    (info.st_dev, info.st_ino) == before and info.st_size == self.sizes[role] and
                    metadata(info) == self.last_metadata[role] and
                    metadata(os.stat(NAMES[role], dir_fd=self.anchor.fd, follow_symlinks=False)) == metadata(info),
                    "CAPTURE_DRIFT")
            allocated += info.st_blocks * 512
        self.max_allocated = max(allocated, self.max_allocated)
        require(allocated <= 4194304 and sum(self.sizes.values()) <= 4194304, "CAPTURE_ALLOCATION")

    def create(self, role):
        self.check()
        require(not self.poisoned and role not in self.attempted and role in NAMES, "CAPTURE_REPLAY")
        self.attempted.add(role)
        try:
            fd = os.open(NAMES[role], os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NOATIME,
                         0o600, dir_fd=self.anchor.fd)
            self.fds[role] = fd
            info = os.fstat(fd)
            self.infos[role] = (info.st_dev, info.st_ino)
            self.sizes[role] = 0
            self.hashes[role] = hashlib.sha256()
            self.last_metadata[role] = metadata(info)
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
            self.last_metadata[role] = metadata(os.fstat(self.fds[role]))
            self.check(final)

    def sync(self, final=False):
        for role, fd in self.fds.items():
            self.check(final)
            actual = hashlib.sha256()
            offset = 0
            while offset < self.sizes[role]:
                self.check(final)
                raw = os.pread(fd, min(65536, self.sizes[role] - offset), offset)
                require(raw, "CAPTURE_SHORT_READ")
                actual.update(raw)
                offset += len(raw)
            require(actual.hexdigest() == self.hashes[role].hexdigest(), "CAPTURE_DIGEST")
            self.check(final)
        for fd in list(self.fds.values()) + [self.anchor.fd]:
            self.check(final)
            os.fsync(fd)
            self.check(final)

    def close(self):
        for fd in self.fds.values():
            os.close(fd)
        self.fds.clear()


def parse_json(raw):
    require(type(raw) is bytes and len(raw) <= 2097152, "RESULT_SIZE")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "RESULT_DUPLICATE")
            result[key] = value
        return result
    def invalid(_):
        raise CaptureError("RESULT_NUMBER")
    return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                      parse_constant=invalid, parse_float=invalid)


def validate_snapshot(raw, sha):
    result = parse_json(raw)
    require(type(result) is dict and set(result) == {"schema", "session", "source_sha256", "euid", "limits",
            "elapsed_ns", "status", "directory", "files"}, "RESULT_FIELDS")
    require(result["schema"] == reader.SCHEMA and result["session"] == SESSION and
            result["status"] == "COMPLETE" and result["source_sha256"] == sha and
            type(result["euid"]) is int and result["euid"] == 0 and result["limits"] == reader.LIMITS and
            type(result["limits"]) is dict and all(type(v) is int for v in result["limits"].values()) and
            type(result["elapsed_ns"]) is int and 0 <= result["elapsed_ns"] < 20_000_000_000, "RESULT_IDENTITY")
    directory = result["directory"]
    require(type(directory) is dict and set(directory) == {"state", "names"} and
            directory["state"] in ("ABSENT", "PRESENT"), "RESULT_DIRECTORY")
    names = directory["names"]
    require(type(names) is list and len(names) <= 256 and all(type(n) is str and n.isascii() and
            n not in ("", ".", "..") and "/" not in n and "\0" not in n for n in names), "RESULT_DIRECTORY")
    require(names == sorted(set(names)) and len(canonical(names)) <= 65536 and
            (directory["state"] == "PRESENT" or names == []), "RESULT_DIRECTORY")
    paths = [reader.MAIN] + [reader.DIRECTORY + "/" + n for n in names if n.endswith(".conf")]
    require(type(result["files"]) is list and 1 <= len(result["files"]) == len(paths) <= 65, "RESULT_FILES")
    total = 0
    raws = {}
    for record, path in zip(result["files"], paths):
        require(type(record) is dict and set(record) == {"path", "bytes", "sha256", "base64", "before", "after", "final"}
                and record["path"] == path and type(record["bytes"]) is int and
                0 <= record["bytes"] <= 262144 and type(record["base64"]) is str, "RESULT_FILE")
        raw_file = base64.b64decode(record["base64"], validate=True)
        require(len(raw_file) == record["bytes"] and digest(raw_file) == record["sha256"], "RESULT_DIGEST")
        before = record["before"]
        require(type(before) is dict and set(before) == set(reader.META) and
                all(type(v) is int and 0 <= v < 2**64 for v in before.values()), "RESULT_METADATA")
        require(all(type(record[key]) is dict and set(record[key]) == set(reader.META) and
                    all(type(v) is int and 0 <= v < 2**64 for v in record[key].values())
                    for key in ("after", "final")), "RESULT_METADATA")
        require(before == record["after"] == record["final"] and stat.S_ISREG(before["mode"]) and
                not before["mode"] & 0o022 and before["uid"] == 0 and before["nlink"] == 1 and
                before["size"] == len(raw_file), "RESULT_METADATA")
        total += len(raw_file)
        require(total <= 1048576, "RESULT_TOTAL")
        raws[path] = raw_file
    return raws


def analyze_snapshot(raw, sha):
    """One pair of offline checks, at most five seconds for each entire check."""
    raws = validate_snapshot(raw, sha)
    results = []
    repo = Path(__file__).resolve().parents[2]
    for commit in PARSERS:
        start = time.monotonic()
        try:
            source = subprocess.run(["git", "-c", "maintenance.auto=false", "-c", "gc.auto=0", "show",
                                    commit + ":tests/e3_host/q2_core_delivery_dispatcher.py"], cwd=repo,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            require(source.returncode == 0 and len(source.stdout) <= 524288, "PARSER_SOURCE")
            remaining = 5 - (time.monotonic() - start)
            require(remaining > 0, "PARSER_DEADLINE")
            data = canonical({"source": source.stdout.decode("utf-8"),
                              "files": [(p, base64.b64encode(v).decode("ascii")) for p, v in raws.items()]})
            answer = subprocess.run([sys.executable, "-I", "-B", "-c", PARSER_WORKER], input=data,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=remaining)
            require(answer.returncode == 0 and not answer.stderr and len(answer.stdout) <= 1024 and
                    time.monotonic() - start < 5, "PARSER_RESULT")
            value = parse_json(answer.stdout)
            require(set(value) == {"state", "code"} and value["state"] in ("ACCEPTED", "REJECTED") and
                    type(value["code"]) is str and len(value["code"]) <= 512 and
                    re.fullmatch(r"[A-Z0-9_]+", value["code"]), "PARSER_RESULT")
            results.append(dict(baseline=commit, **value))
        except (Exception, KeyboardInterrupt):
            results.append(dict(baseline=commit, state="UNKNOWN", code="OFFLINE_ANALYSIS_INCOMPLETE"))
            break
    return results


def run_once(anchor, source, binding, deadline, *, popen=subprocess.Popen, analyze=analyze_snapshot):
    """One irreversible marker even if process creation or output capture fails."""
    argv, env = binding["argv"], binding["environment"]
    cap = Capture(anchor, deadline)
    process = None
    output = bytearray()
    status = {"schema": "lhq-sshd-source-capture-receipt-v1", "session": SESSION,
              "state": "FAILED", "reason": "NOT_STARTED", "requests_attempted": 0,
              "marker_creation_attempted": False, "marker_created": False,
              "exit": None, "stdout_eof": False, "stderr_eof": False,
              "snapshot_complete": False, "remote_supervision_proven": False,
              "remote_exit": "UNKNOWN", "complete_host_admission_proven": False,
              "exclusive_reservation_proven": False, "old_commitments_refunded": False,
              "R": R, "A": A, "C": C, "D": binding["D"], "reader_sha256": digest(source),
              "argv_environment_sha256": digest(canonical({"argv": argv, "environment": env})),
              "clock_origins_ns": deadline.origins}
    try:
        anchor.recheck()
        for name in NAMES.values():
            anchor.absent(name)
        anchor.capacity()
        cap.create("marker")
        cap.write("marker", canonical({key: status[key] for key in
            ("schema", "session", "R", "A", "C", "D", "reader_sha256", "argv_environment_sha256", "clock_origins_ns")}))
        cap.sync()
        for role in ("stdout", "stderr", "receipt"):
            cap.create(role)
        cap.sync()
        anchor.recheck(after_create=True)
        status["requests_attempted"] = 1
        process = popen(argv, executable=f"/proc/self/fd/{anchor.ssh}", pass_fds=(anchor.ssh,),
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        env=env, cwd=anchor.path, start_new_session=True)
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
                    cap.write(role, chunk)
                    if role == "stdout":
                        output.extend(chunk)
        status["exit"] = process.wait(timeout=deadline.remaining())
        require(status["exit"] == 0, "SSH_EXIT")
        validate_snapshot(bytes(output), digest(source))
        deadline.check()
        status.update(state="COMPLETE", reason="SNAPSHOT_VERIFIED", snapshot_complete=True,
                      remote_exit="READER_REPORTED_COMPLETE")
    except (Exception, KeyboardInterrupt) as error:
        status["reason"] = str(error) if type(error) is CaptureError else "LOCAL_IO_OR_TRANSPORT"
    finally:
        status["marker_creation_attempted"] = "marker" in cap.attempted
        status["marker_created"] = True if "marker" in cap.fds else (None if "marker" in cap.attempted else False)
        if process is not None:
            try:
                if process.poll() is None:
                    process.kill()  # Only the Popen child owned by this invocation.
                status["exit"] = process.wait(timeout=deadline.remaining(60))
            except (Exception, KeyboardInterrupt):
                status.update(state="UNKNOWN", snapshot_complete=False, remote_exit="UNKNOWN", reason="STOP_UNCONFIRMED")
            for stream in (process.stdout, process.stderr):
                stream.close()
        try:
            deadline.remaining(60)
            status["files"] = {role: {"bytes": cap.sizes[role], "sha256": cap.hashes[role].hexdigest()}
                               for role in cap.sizes if role != "receipt"}
            status["observed_allocated_peak_before_receipt_bytes"] = cap.max_allocated
            status["host_deadline_met"] = True
            if "receipt" in cap.fds:
                cap.write("receipt", canonical(status), final=True)
                cap.sync(final=True)
        except (Exception, KeyboardInterrupt):
            status.update(state="UNKNOWN", snapshot_complete=False, reason="SEAL_INCOMPLETE", host_deadline_met=False)
        try:
            cap.close()
        except OSError:
            status.update(state="UNKNOWN", snapshot_complete=False, reason="LOCAL_CLOSE_INCOMPLETE")
    # Capture is finished and all owned fds/transport are closed. This does not
    # extend its deadline or create another capture file or remote connection.
    if status["state"] == "COMPLETE":
        status["diagnosis"] = analyze(bytes(output), digest(source))
    return status


def freeze_repo(expected):
    require(re.fullmatch(r"[0-9a-f]{40}", expected) is not None, "D_FORMAT")
    repo = Path(__file__).resolve().parents[2]
    def git(*args):
        result = subprocess.run(["git", "-c", "maintenance.auto=false", "-c", "gc.auto=0", *args], cwd=repo,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        require(result.returncode == 0, "SOURCE_BASELINE")
        return result.stdout
    require(git("rev-parse", "HEAD").decode().strip() == expected, "D_HEAD")
    git("diff", "--quiet", "HEAD")
    git("merge-base", "--is-ancestor", C, expected)
    require(expected != C, "D_MISSING")
    for name, sha in DOC_PINS.items():
        path = "docs/a2-execution/q2-core-sshd-source-capture/" + name
        require(digest(git("show", expected + ":" + path)) == sha, "A_CHANGED")
    sources = {}
    for name, cap in (("q2_sshd_source_reader.py", 32768 - len(LOADER.encode())),
                      ("q2_sshd_source_capture.py", 65536)):
        path = Path(__file__).with_name(name)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC)
        try:
            raw, _ = stable_read(fd, cap, lambda: None)
        finally:
            os.close(fd)
        require(raw == git("show", expected + ":tests/e3_host/" + name), "SOURCE_DRIFT")
        sources[name] = raw
    return sources


def preflight(anchor, source, commit):
    env = {key: os.environ[key] for key in ("HOME", "USER", "LOGNAME")}
    env.update(PATH="/usr/bin:/bin", LANG="C", LC_ALL="C")
    argv = make_argv(anchor.path, source)
    require(sum(len(x.encode()) + 1 for x in argv) + sum(len((k + "=" + v).encode()) + 1 for k, v in env.items())
            <= min(65536, os.sysconf("SC_ARG_MAX")), "ARGV_LIMIT")
    # -G evaluates this exact fixed config without connecting. No Match/exec/local command exists.
    result = subprocess.run(argv[:1] + ["-G"] + argv[1:], executable=f"/proc/self/fd/{anchor.ssh}",
                            pass_fds=(anchor.ssh,), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=min(5, anchor.deadline.remaining()), env=env)
    require(result.returncode == 0 and len(result.stdout) <= 65536 and len(result.stderr) <= 4096, "SSH_OPTIONS")
    anchor.recheck()
    for name in NAMES.values():
        anchor.absent(name)
    anchor.capacity()
    return {"D": commit, "argv": argv, "environment": env}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    anchor = None
    execution_entered = False
    try:
        sources = freeze_repo(args.expected_commit)
        deadline = Deadline()
        anchor = Anchor(args.anchor, deadline)
        source = sources["q2_sshd_source_reader.py"]
        binding = preflight(anchor, source, args.expected_commit)
        if not args.execute:
            result = dict(state="LOCAL_PREFLIGHT_PASSED", session=SESSION, requests_attempted=0,
                          reader_sha256=digest(source), D=args.expected_commit)
        else:
            execution_entered = True
            result = run_once(anchor, source, binding, deadline)
        # The receipt's machine metadata and all raw streams stay private.
        public = {key: result[key] for key in ("state", "reason", "requests_attempted", "snapshot_complete", "D", "diagnosis") if key in result}
        print(canonical(public).decode("ascii"), end="")
        return 0 if result["state"] in ("LOCAL_PREFLIGHT_PASSED", "COMPLETE") else 3
    except (Exception, KeyboardInterrupt) as error:
        reason = str(error) if type(error) is CaptureError else "LOCAL_PREFLIGHT_IO"
        print(canonical(dict(state="UNKNOWN" if execution_entered else "BLOCKED", reason=reason,
                             requests_attempted=None if execution_entered else 0)).decode("ascii"), end="")
        return 3
    finally:
        if anchor is not None:
            anchor.close()


if __name__ == "__main__":
    sys.exit(main())
