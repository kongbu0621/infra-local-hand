"""Create-only, bounded preparation of one explicitly selected isolated guest.

The existing management delivery must independently bound this process. Local
deadlines bound command/capture work; they cannot turn a blocked filesystem
syscall into an interruptible operation. Partial objects are never removed or
reused. The separate driver assembles and runs the existing Q2 chain.
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import signal
import socket
import stat
import subprocess
import sys
import time


def sibling(name):
    spec = importlib.util.spec_from_file_location("_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = sibling("q2_prepare_contract")
SCHEMA = "local-hand-q2-fixture-preparation/v1"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C", "SYSTEMD_COLORS": "0"}


def reason(error):
    value = str(error)
    return value if isinstance(error, ValueError) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else type(error).__name__


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(info, name=None):
    result = {key: getattr(info, "st_" + field) for key, field in
              (("device", "dev"), ("inode", "ino"), ("uid", "uid"), ("gid", "gid"), ("mode", "mode"))}
    if name is not None: result["path"] = str(name)
    return result


def opened(name, *, directory=False, owner=0, noatime=False):
    """Walk protected ancestry without following symlinks or special files."""
    c.path(str(name), root=True)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    if noatime: flags |= os.O_NOATIME
    fd = os.open("/", flags | os.O_DIRECTORY)
    try:
        for index, part in enumerate(Path(name).parts[1:]):
            isdir = directory or index < len(Path(name).parts) - 2
            child = os.open(part, flags | (os.O_DIRECTORY if isdir else 0), dir_fd=fd)
            os.close(fd); fd = child
            info = os.fstat(fd)
            c.require(info.st_uid in (0, owner) and not info.st_mode & 0o022
                and (stat.S_ISDIR(info.st_mode) if isdir else stat.S_ISREG(info.st_mode)
                     and info.st_nlink == 1 and not info.st_mode & 0o6000), "PREPARE_UNPROTECTED_PATH")
        return fd
    except BaseException:
        os.close(fd); raise


def read(name, maximum, *, owner=0, noatime=False):
    fd = opened(name, owner=owner, noatime=noatime)
    try:
        before = os.fstat(fd); result = bytearray()
        c.require(before.st_size <= maximum, "PREPARE_READ_LIMIT")
        while len(result) <= maximum:
            block = os.read(fd, min(65536, maximum + 1 - len(result)))
            if not block: break
            result.extend(block)
        after = os.fstat(fd)
        c.require(len(result) <= maximum and all(getattr(before, k) == getattr(after, k) for k in
            ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")), "PREPARE_READ_CHANGED")
        return bytes(result)
    finally:
        os.close(fd)


def kernel(name, maximum=65536):
    # Only fixed internal proc/sys paths; no plan-controlled path is passed here.
    with open(name, "rb", buffering=0) as stream:
        raw = stream.read(maximum + 1)
    c.require(len(raw) <= maximum, "PREPARE_KERNEL_LIMIT")
    return raw


def create_file(name, raw, *, mode=0o600, owner=0, gid=0):
    parent = opened(str(Path(name).parent), directory=True, owner=owner)
    fd = None
    try:
        fd = os.open(Path(name).name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode, dir_fd=parent)
        os.fchmod(fd, mode); os.fchown(fd, owner, gid)
        offset = 0
        while offset < len(raw):
            count=os.write(fd,raw[offset:]);c.require(count>0,"PREPARE_WRITE_ZERO");offset+=count
        os.fsync(fd); os.fsync(parent)
    finally:
        if fd is not None: os.close(fd)
        os.close(parent)


def create_directory(name, *, mode=0o700, owner=0, gid=0):
    parent = opened(str(Path(name).parent), directory=True, owner=owner)
    try:
        os.mkdir(Path(name).name, mode=mode, dir_fd=parent)
        fd = os.open(Path(name).name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
        try:
            os.fchmod(fd, mode); os.fchown(fd, owner, gid); os.fsync(fd)
            result = identity(os.fstat(fd), name)
        finally: os.close(fd)
        os.fsync(parent)
        return result
    finally: os.close(parent)


class Quota:
    """Linux x86-64 UAPI Q_GETNEXTQUOTA/Q_GETQUOTA and XGETQSTATV only.

    No mutating quota command is callable here. Mutations are separately recorded
    invocations of the pinned setquota utility, once per new project.
    """
    def __init__(self, device):
        import ctypes
        import platform
        c.require(sys.platform.startswith("linux") and platform.machine() == "x86_64", "PREPARE_QUOTA_ABI")
        self.ct = ctypes
        class Block(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                ("hard", "soft", "space", "ihard", "isoft", "inodes", "btime", "itime")]
            _fields_ += [("valid", ctypes.c_uint32), ("project", ctypes.c_uint32)]
        self.Block = Block
        c.require(ctypes.sizeof(Block) == 72, "PREPARE_QUOTA_ABI")
        self.lib = ctypes.CDLL(None, use_errno=True)
        self.lib.quotactl.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        self.lib.quotactl.restype = ctypes.c_int
        self.device = os.fsencode(device)

    def call(self, command, project, buffer):
        self.ct.set_errno(0)
        rc = self.lib.quotactl(self.ct.c_int((command << 8) | 2), self.device,
                              self.ct.c_int(project), self.ct.byref(buffer))
        if rc != 0: raise OSError(self.ct.get_errno(), "quota observation failed")

    def block(self, project):
        result = self.Block(); self.call(0x800007, project, result)
        return {name: getattr(result, name) for name, _ in result._fields_ if name != "project"}

    def unused(self,project):
        try: result=self.block(project)
        except OSError as error:
            if error.errno==errno.ESRCH:return
            raise
        c.require(all(value==0 for key,value in result.items() if key!="valid"),"PREPARE_PROJECT_BECAME_OCCUPIED")

    def inventory(self, guard):
        rows = []; start = 0
        for _ in range(128):
            guard(); result = self.Block()
            try: self.call(0x800009, start, result)
            except OSError as error:
                if error.errno == errno.ENOENT: return rows
                raise
            c.require(start <= result.project < 2**32 - 1, "PREPARE_QUOTA_ORDER")
            rows.append({name: getattr(result, name) for name, _ in result._fields_})
            start = result.project + 1
        raise ValueError("PREPARE_QUOTA_INVENTORY_LIMIT")

    def enforcement(self):
        buffer = self.ct.create_string_buffer(160); buffer[0] = b"\x01"
        self.call((ord("X") << 8) | 8, 0, buffer)
        raw = bytes(buffer); flags = int.from_bytes(raw[2:4], sys.byteorder)
        c.require(raw[0] == 1 and flags & 48 == 48, "PREPARE_QUOTA_ENFORCEMENT")
        return flags


class LinuxBackend:
    def __init__(self, plan):
        self.plan = plan
        self.deadline = time.monotonic_ns() + plan["budgets"]["preparation_seconds"] * 10**9
        self.reservation = None
        self.sequence = 0
        self.observed = {}
        self.preflight_commands=[]
        self.log_byte_limit=plan["budgets"]["state_bytes"]*3//4
        self.log_inode_limit=plan["budgets"]["state_inodes"]*3//4
        self.log_bytes=0
        self.max_events=0
        self.log_block=4096
        self.last_command_failure=None

    def guard(self):
        c.require(time.monotonic_ns() < self.deadline, "PREPARE_DEADLINE")

    def event(self, kind, value):
        # The independent original owner still bounds finalization. The work
        # deadline must not prevent saving the timeout's actual pipe/exit facts.
        if kind!="command-result": self.guard()
        if self.reservation is None: return
        raw=c.encoded(value)
        self.sequence += 1
        size=((len(raw)+self.log_block-1)//self.log_block)*self.log_block
        c.require(self.sequence <= self.max_events and self.sequence+4<=self.log_inode_limit
                  and self.log_bytes+size+c.LIMIT <= self.log_byte_limit,"PREPARE_EVENT_LIMIT")
        create_file(self.reservation / (f"{self.sequence:04d}-" + kind + ".json"), raw)
        self.log_bytes+=size

    def tool(self, name):
        return self.plan["tools"][name]["path"]

    def command(self, argv, *, env=None):
        self.guard()
        c.require(type(argv) in (list, tuple) and 1 <= len(argv) <= 128
                  and all(type(a) is str and len(a) <= 65536 and "\0" not in a for a in argv), "PREPARE_COMMAND")
        argv_record=c.encoded({"argv":list(argv)})
        c.require(len(argv_record)<=32768,"PREPARE_COMMAND_ARGV_LIMIT")
        if self.reservation is not None:
            # Admit intent, maximum result, block overhead and final report
            # before process creation; exhausted capture budgets never launch.
            reserve=len(argv_record)*2+2*self.plan["budgets"]["command_output_bytes"]+3*self.log_block
            c.require(self.sequence+2<=self.max_events and self.sequence+6<=self.log_inode_limit
                      and self.log_bytes+reserve+c.LIMIT<=self.log_byte_limit,"PREPARE_COMMAND_RECORD_BUDGET")
        self.event("command-intent", {"argv": list(argv)})
        deadline = min(self.deadline, time.monotonic_ns() + self.plan["budgets"]["command_seconds"] * 10**9)
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=ENV if env is None else env, close_fds=True, start_new_session=True)
        selector = selectors.DefaultSelector(); output = {"stdout": bytearray(), "stderr": bytearray()}
        eof = set(); failure = None
        for name in output:
            stream = getattr(proc, name); os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, name)
        try:
            while len(eof) != 2 or proc.poll() is None:
                if time.monotonic_ns() >= deadline:
                    failure = "PREPARE_COMMAND_TIMEOUT"; break
                for key, _ in selector.select(min(0.05, max(0, (deadline-time.monotonic_ns())/10**9))):
                    block = os.read(key.fd, 4096)
                    if not block:
                        eof.add(key.data); selector.unregister(key.fileobj); continue
                    room = self.plan["budgets"]["command_output_bytes"] - sum(map(len, output.values()))
                    output[key.data].extend(block[:room])
                    if len(block) > room: failure = "PREPARE_COMMAND_OUTPUT_LIMIT"; break
                if failure: break
            if failure:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                try: proc.wait(timeout=1)
                except subprocess.TimeoutExpired: pass
            result = {"argv": list(argv), "returncode": proc.poll(), "eof": sorted(eof), "failure": failure,
                      **{name: bytes(raw).hex() for name, raw in output.items()}}
            unsuccessful=failure is not None or len(eof)!=2 or proc.returncode!=0
            if unsuccessful:
                # The durable command result keeps the original bounded bytes.
                # Include a small readable diagnosis in the batch receipt too,
                # so a failed command does not require another host round trip.
                self.last_command_failure={"argv":list(argv),"returncode":proc.poll(),"eof":sorted(eof),
                    "failure":failure,"record":None if self.reservation is None else
                        str(self.reservation/f"{self.sequence+1:04d}-command-result.json"),
                    "record_sha256":sha(c.encoded(result)),"record_saved":False,
                    "stdout":bytes(output["stdout"][:4096]).decode("utf-8",errors="replace"),
                    "stderr":bytes(output["stderr"][:4096]).decode("utf-8",errors="replace"),
                    "summary_truncated":{name:len(value)>4096 for name,value in output.items()}}
            if self.reservation is None:
                self.preflight_commands.append(len(argv_record)+len(c.encoded(result)))
            self.event("command-result", result)
            if unsuccessful:
                self.last_command_failure["record_saved"]=self.reservation is not None
            c.require(failure is None and len(eof) == 2 and proc.returncode == 0,
                      failure or "PREPARE_COMMAND_FAILED")
            return bytes(output["stdout"])
        finally:
            selector.close()
            for name in output: getattr(proc, name).close()

    def absent(self, name, *, device=None):
        c.require(not os.path.lexists(name), "PREPARE_OBJECT_EXISTS")
        fd = opened(str(Path(name).parent), directory=True)
        try:
            if device is not None: c.require(os.fstat(fd).st_dev==device,"PREPARE_NEW_PARENT_MOUNT")
        finally: os.close(fd)

    def snapshot(self):
        result = []; total = 0; count = 0
        for selected in self.plan["retained"]:
            self.guard(); st = os.lstat(selected["path"])
            c.require(stat.S_ISDIR(st.st_mode) and (st.st_dev, st.st_ino) == (selected["device"], selected["inode"]),
                      "PREPARE_RETAINED_IDENTITY")
            stack = [Path(selected["path"])]; files = []
            while stack:
                self.guard(); name = stack.pop(); info = name.lstat(); count += 1
                c.require(count <= self.plan["budgets"]["retained_scan_entries"] and not stat.S_ISLNK(info.st_mode)
                          and info.st_dev == selected["device"], "PREPARE_RETAINED_TREE")
                row = identity(info, name)
                if stat.S_ISDIR(info.st_mode):
                    with os.scandir(name) as entries:
                        for entry in entries:
                            c.require(len(stack) + count < self.plan["budgets"]["retained_scan_entries"], "PREPARE_RETAINED_SCAN_LIMIT")
                            stack.append(Path(entry.path))
                else:
                    c.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "PREPARE_RETAINED_TYPE")
                    total += info.st_size
                    c.require(total <= self.plan["budgets"]["retained_scan_bytes"], "PREPARE_RETAINED_BYTES")
                    row["sha256"] = sha(read(name, info.st_size, owner=info.st_uid, noatime=True))
                    row["size"] = info.st_size
                files.append(row)
            result.append({"root": selected, "entries": len(files), "sha256": sha(c.encoded(sorted(files, key=lambda x:x["path"])))})
        return result

    def preflight(self):
        self.guard(); p = self.plan
        c.require(sys.platform.startswith("linux") and os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 0,
                  "PREPARE_ROOT_LINUX_REQUIRED")
        c.require(kernel("/proc/1/comm").strip() == b"systemd", "PREPARE_SYSTEMD_REQUIRED")
        ns = os.stat("/proc/self/ns/user"); init = os.stat("/proc/1/ns/user")
        actual = dict(hostname=socket.gethostname(), boot_id=kernel("/proc/sys/kernel/random/boot_id").decode().strip(),
            initial_userns=dict(device=ns.st_dev, inode=ns.st_ino),
            dmi_vendor=kernel("/sys/class/dmi/id/sys_vendor").decode().strip(),
            dmi_product=kernel("/sys/class/dmi/id/product_name").decode().strip())
        c.require(actual == p["host"] and (ns.st_dev,ns.st_ino) == (init.st_dev,init.st_ino), "PREPARE_GUEST_CHANGED")
        import pwd, grp
        account = p["account"]
        for lookup, key in ((pwd.getpwnam,account["name"]),(pwd.getpwuid,account["uid"]),
                            (grp.getgrnam,account["name"]),(grp.getgrgid,account["gid"])):
            try: lookup(key)
            except KeyError: continue
            raise ValueError("PREPARE_ACCOUNT_EXISTS")
        for tool in p["tools"].values():
            raw = read(tool["path"], 64*1024**2)
            c.require(raw.startswith(b"\x7fELF") and sha(raw) == tool["sha256"]
                      and os.stat(tool["path"]).st_mode & 0o111, "PREPARE_TOOL_CHANGED")
        for role,filename in (("git","git"),("setpriv","setpriv"),("systemctl","systemctl"),("systemd_run","systemd-run")):
            c.require(p["tools"][role]["path"]==str(Path("/usr/bin",filename).resolve(strict=True)),"PREPARE_FIXED_TOOL_PATH")
        for item in p["directories"].values():
            self.absent(item["path"],device=p["mounts"][item["filesystem"]]["device"])
        self.absent(p["candidate"]["destination"],device=p["mounts"]["system"]["device"])
        ordinary_paths=[p["candidate"]["destination"],*[item["path"] for role,item in p["directories"].items()
                         if item["owner"]=="ordinary" or role in ("control","session","declarations")]]
        for target in ordinary_paths:
            for ancestor in reversed(Path(target).parents):
                info=ancestor.stat()
                shift=6 if info.st_uid==account["uid"] else 3 if info.st_gid==account["gid"] else 0
                c.require(info.st_mode>>shift&5==5,"PREPARE_ORDINARY_ANCESTOR_ACCESS")
                for key in ("system.posix_acl_access","system.posix_acl_default"):
                    try:os.getxattr(ancestor,key,follow_symlinks=False)
                    except OSError as error:
                        if error.errno in (errno.ENODATA,errno.ENOTSUP,errno.EOPNOTSUPP):continue
                        raise
                    raise ValueError("PREPARE_ANCESTOR_ACL_UNPROVEN")
        for parent in p["parents"].values():
            # Exact absent unit files, drop-ins and currently loaded units.
            for prefix in ("/etc/systemd/system/", "/run/systemd/system/", "/usr/lib/systemd/system/"):
                c.require(not os.path.lexists(prefix+parent["unit"]) and not os.path.lexists(prefix+parent["unit"]+".d"),
                          "PREPARE_UNIT_EXISTS")
        # An exact unmatched systemctl pattern may return nonzero on some
        # supported systemd versions. Enumerate a finite bounded list once and
        # compare exact names, instead of treating 'absent' as command failure.
        candidates={parent["unit"] for parent in p["parents"].values()}
        for arguments in (("list-units","--all","--plain","--no-legend","--type=slice"),
                          ("list-unit-files","--no-legend","--type=slice")):
            data=self.command([self.tool("systemctl"),"--system",*arguments])
            names={line.split()[0] for line in data.decode().splitlines() if line.split()}
            c.require(not candidates&names,"PREPARE_UNIT_LOADED")
        instance = f"user@{account['uid']}.service"
        for prefix in ("/etc/systemd/system/","/run/systemd/system/","/usr/lib/systemd/system/"):
            for suffix in ("", ".d"):
                c.require(not os.path.lexists(prefix+instance+suffix),"PREPARE_MANAGER_CONFIGURATION_EXISTS")
        self.absent("/etc/systemd/system/"+instance+".d")
        c.require(self.command([self.tool("systemctl"), "--system", "show", instance, "--property=ActiveState", "--value"]).strip() == b"inactive",
                  "PREPARE_MANAGER_ALREADY_ACTIVE")
        rows = kernel("/proc/self/mountinfo", 1024*1024).decode().splitlines(); mounts = {}
        for role, expected in p["mounts"].items():
            selected = [line.split() for line in rows if line.split()[4] == expected["path"]]
            c.require(len(selected) == 1, "PREPARE_MOUNT_AMBIGUOUS")
            row = selected[0]; sep = row.index("-")
            major, minor = map(int, row[2].split(":")); device = os.makedev(major,minor)
            c.require(row[3] == "/" and device == expected["device"] == os.stat(expected["path"]).st_dev
                and row[sep+1] == expected["filesystem"] and row[sep+2] == expected["source"]
                and "rw" in row[5].split(","), "PREPARE_MOUNT_CHANGED")
            source_info = os.stat(expected["source"])
            c.require(stat.S_ISBLK(source_info.st_mode) and source_info.st_rdev == device, "PREPARE_BLOCK_DEVICE")
            observed_uuid = self.command([self.tool("blkid"), "-p", "-s", "UUID", "-o", "value", expected["source"]]).decode().strip()
            c.require(observed_uuid == expected["uuid"], "PREPARE_FILESYSTEM_UUID")
            if role == "quota": c.require("prjquota" in set(row[5].split(",")+row[sep+3].split(",")), "PREPARE_PROJECT_MOUNT")
            fs = os.statvfs(expected["path"])
            mounts[role] = dict(expected, available_bytes=fs.f_bavail*fs.f_frsize, free_inodes=fs.f_favail,
                                total_bytes=fs.f_blocks*fs.f_frsize, total_inodes=fs.f_files, block_bytes=fs.f_frsize)
        quota = Quota(p["mounts"]["quota"]["source"]); quota.enforcement()
        inventory = quota.inventory(self.guard); old = {r["project"]: r for r in inventory}
        for retained in p["retained_domains"]:
            row = old.get(retained["project_id"])
            c.require(row is not None and row["hard"]*1024 == retained["hard_bytes"]
                      and row["ihard"] == retained["inode_hard_limit"], "PREPARE_RETAINED_QUOTA_CHANGED")
        for root in p["roots"]:
            c.require(root["project_id"] not in old, "PREPARE_PROJECT_EXISTS")
            try: row = quota.block(root["project_id"])
            except OSError as error:
                if error.errno == errno.ESRCH: row = {"valid":0}
                else: raise
            c.require(all(amount == 0 for key, amount in row.items() if key != "valid"), "PREPARE_PROJECT_NOT_EMPTY")
        # Conservative full old commitments are charged against current free,
        # without adding old logical and allocated payloads a second time.
        commitments = {k: dict(bytes=0,inodes=0) for k in mounts}
        commitments["quota"] = dict(bytes=sum(r["hard"]*1024 for r in inventory) + sum(r["hard_bytes"] for r in p["roots"]),
                                    inodes=sum(r["ihard"] for r in inventory) + sum(r["inode_hard_limit"] for r in p["roots"]))
        b = p["budgets"]
        fee_devices = {"installation": {"system"},
            "state": {p["directories"][role]["filesystem"] for role in ("reservation","state","authority")},
            "journal": {p["directories"]["journal"]["filesystem"]},
            "capture": {p["directories"][role]["filesystem"] for role in ("capture","declarations","session","control")}}
        for label, fsroles in fee_devices.items():
            for fsrole in fsroles:
                commitments[fsrole]["bytes"] += b[label+"_bytes"]
                commitments[fsrole]["inodes"] += b[label+"_inodes"]
        for role, costs in commitments.items():
            c.require(costs["bytes"] <= mounts[role]["available_bytes"] and costs["inodes"] <= mounts[role]["free_inodes"],
                      "PREPARE_CAPACITY_INSUFFICIENT")
        # Candidate identity checks before the first persistent object.
        build=sibling("q2_prepare_build"); source=Path(p["candidate"]["source"])
        build.parents(source,protected=True)
        staged=build.bounded_inventory(source,protected=True)
        c.require(staged["bytes"]+os.stat(p["candidate"]["wheel"]).st_size < b["installation_bytes"], "PREPARE_STAGING_BUDGET")
        source_files=build.verify_source(source,p["candidate"]["commit"],p["candidate"]["tree"],self.command)
        build.verify_wheel(Path(p["candidate"]["wheel"]),p["candidate"]["wheel_sha256"],p["candidate"]["commit"],source_files)
        retained = self.snapshot()
        # Four later source-verification passes have the same bounded command
        # topology and content. The allowance also covers 128 fixed remaining
        # commands, all directory/step/quota receipts and reserved final output.
        commands=4*len(self.preflight_commands)+128
        self.max_events=commands*2+128
        self.log_block=mounts[p["directories"]["reservation"]["filesystem"]]["block_bytes"]
        estimate=(4*sum(self.preflight_commands)+128*(2*b["command_output_bytes"]+32768)
                  +3*c.LIMIT+(self.max_events+4)*self.log_block)
        c.require(self.max_events+4<=self.log_inode_limit and estimate<=self.log_byte_limit,"PREPARE_LOG_CAPACITY")
        self.observed = dict(host=actual, mounts=mounts, retained_before=retained,
                             capacity_observed=dict(commitments=commitments, quota_inventory=inventory,
                                 preparation_events=self.max_events,preparation_log_bytes=estimate))
        return self.observed

    def reserve(self, plan):
        path = Path(plan["directories"]["reservation"]["path"])
        create_directory(path); self.reservation = path
        for name,value in (("intent",plan),("preflight",self.observed)):
            raw=c.encoded(value);create_file(path/(name+".json"),raw)
            self.log_bytes+=((len(raw)+self.log_block-1)//self.log_block)*self.log_block

    def account(self):
        p = self.plan; account = p["account"]
        self.command([self.tool("groupadd"), "--gid", str(account["gid"]), account["name"]])
        self.command(self.useradd_argv())
        return self.verify_account()

    def useradd_argv(self):
        p = self.plan; account = p["account"]
        # CREATE_MAIL_SPOOL is a useradd-defaults setting, not a login.defs
        # key accepted by -K. Shadow's --system mode suppresses the mailbox
        # and subordinate-ID allocation (without -F), while explicit --uid
        # and --gid retain the planned non-root execution identity.
        return [self.tool("useradd"), "--system", "--uid", str(account["uid"]), "--gid", str(account["gid"]),
                "--no-user-group", "--no-log-init", "--no-create-home",
                "--home-dir", p["directories"]["state"]["path"],
                "--shell", "/usr/sbin/nologin", "--password", "!", account["name"]]

    def verify_account(self):
        account = self.plan["account"]
        import pwd, grp
        entry = pwd.getpwnam(account["name"])
        c.require((entry.pw_uid,entry.pw_gid) == (account["uid"],account["gid"])
                  and os.getgrouplist(account["name"],account["gid"]) == [account["gid"]], "PREPARE_ORDINARY_IDENTITY")
        return dict(account)

    def directories(self):
        result = {}; account = self.plan["account"]
        for role, item in self.plan["directories"].items():
            self.guard()
            if role == "reservation": result[role] = identity(os.stat(item["path"]),item["path"]); continue
            self.event("directory-intent", dict(role=role, **item))
            owner,gid = (account["uid"],account["gid"]) if item["owner"] == "ordinary" else (0,0)
            result[role] = create_directory(item["path"],mode=item["mode"],owner=owner,gid=gid)
            c.require(result[role]["device"] == self.plan["mounts"][item["filesystem"]]["device"], "PREPARE_NEW_DIRECTORY_MOUNT")
            self.event("directory-result", dict(role=role, **result[role]))
        return result

    def install(self):
        build = sibling("q2_prepare_build"); p = self.plan; candidate = p["candidate"]
        result=build.install_candidate(source=Path(candidate["source"]), source_commit=candidate["commit"],
            source_tree=candidate["tree"],wheel=Path(candidate["wheel"]),wheel_sha256=candidate["wheel_sha256"],
            destination=Path(candidate["destination"]),python=Path(self.tool("python")),compiler=Path(self.tool("compiler")),
            ordinary_uid=p["account"]["uid"],ordinary_gid=p["account"]["gid"],command=self.command)
        amounts=[build.bounded_inventory(Path(candidate[key]),protected=True) for key in ("source","destination")]
        c.require(sum(a["bytes"] for a in amounts)+os.stat(candidate["wheel"]).st_size <= p["budgets"]["installation_bytes"]
                  and sum(a["entries"] for a in amounts)+1 <= p["budgets"]["installation_inodes"], "PREPARE_INSTALLATION_BUDGET")
        return result

    def roots(self):
        import fcntl, struct
        result=[]; p=self.plan; quota=Quota(p["mounts"]["quota"]["source"])
        for root in p["roots"]:
            self.guard(); self.event("quota-intent",root)
            # Recheck after installation/manager-independent work: an ID that
            # became occupied since preflight must never have its limits set.
            quota.unused(root["project_id"])
            info=create_directory(root["path"],owner=p["account"]["uid"],gid=p["account"]["gid"])
            self.command([self.tool("chattr"),"-p",str(root["project_id"]),"+P",root["path"]])
            prior=quota.block(root["project_id"])
            c.require(prior["inodes"]==1 and all(prior[k]==0 for k in ("hard","soft","ihard","isoft","btime","itime")),
                      "PREPARE_PROJECT_ASSIGNMENT_UNCERTAIN")
            self.command([self.tool("setquota"),"-P",str(root["project_id"]),"0",str(root["hard_bytes"]//1024),"0",
                          str(root["inode_hard_limit"]),p["mounts"]["quota"]["path"]])
            fd=opened(root["path"],directory=True,owner=p["account"]["uid"])
            try:
                before=identity(os.fstat(fd),root["path"])
                # Linux FS_IOC_FSGETXATTR, checked x86-64 UAPI layout (28 bytes).
                data=fcntl.ioctl(fd,0x801c581f,bytes(28)); flags,_,_,project,_,_=struct.unpack("=IIIII8s",data)
                values=quota.block(root["project_id"]); enforcement=quota.enforcement()
                after=identity(os.fstat(fd),root["path"])
                c.require(before==after==info and project==root["project_id"] and flags & 512
                    and values["valid"]&5==5 and values["hard"]*1024==root["hard_bytes"]
                    and values["ihard"]==root["inode_hard_limit"], "PREPARE_QUOTA_FACTS")
                row=dict(root,**{k:v for k,v in info.items() if k!="path"},filesystem="ext4",filesystem_uuid=p["mounts"]["quota"]["uuid"],
                         xflags=flags,accounting=bool(enforcement&16),enforcement=bool(enforcement&32),identity_unchanged=True)
                result.append(row); self.event("quota-result",row)
            finally: os.close(fd)
        return result

    def user_command(self,args):
        account=self.plan["account"]
        return self.command([self.tool("setpriv"),"--reuid="+str(account["uid"]),"--regid="+str(account["gid"]),
            "--clear-groups","--inh-caps=-all","--ambient-caps=-all","--bounding-set=-all","--no-new-privs",*args],
            env=dict(ENV,XDG_RUNTIME_DIR="/run/user/"+str(account["uid"])))

    def show(self,unit,*,ordinary=False):
        args=[self.tool("systemctl"),"--user" if ordinary else "--system","show",unit,
              "--property=Id,LoadState,ActiveState,SubState,ControlGroup,User,Delegate,MemoryMax,TasksMax,CPUQuotaPerSecUSec,MemorySwapMax"]
        raw=self.user_command(args) if ordinary else self.command(args)
        return dict(line.split("=",1) for line in raw.decode().splitlines())

    def parents(self):
        p=self.plan; account=p["account"]
        instance=f"user@{account['uid']}.service"
        drop=Path("/etc/systemd/system")/(instance+".d")
        self.event("delegation-intent",{"unit":instance,"dropin":str(drop)})
        create_directory(drop,mode=0o755)
        ordinary=p["parents"]["ordinary"]
        manager_configuration=("[Service]\nDelegate=cpu memory pids\nCPUAccounting=yes\nCPUQuota="
            +format(ordinary["cpu_quota_per_sec_usec"]/10000,"g")+"%\nCPUQuotaPeriodSec=100ms\nMemoryAccounting=yes\nMemoryMax="
            +str(ordinary["memory_bytes"])+"\nMemorySwapMax=0\nTasksAccounting=yes\nTasksMax="+str(ordinary["tasks_max"])+"\n")
        create_file(drop/"50-local-hand-q2.conf",manager_configuration.encode(),mode=0o644)
        for role in c.SYSTEM_PARENTS:
            row=p["parents"][role]
            create_file(Path("/etc/systemd/system")/row["unit"],self.slice_bytes(row),mode=0o644)
        self.command([self.tool("systemctl"),"--system","daemon-reload"])
        self.command([self.tool("systemctl"),"--system","start",*[p["parents"][role]["unit"] for role in c.SYSTEM_PARENTS]])
        self.command([self.tool("systemctl"),"--system","start",f"user-runtime-dir@{account['uid']}.service",instance])
        manager=self.show(instance)
        c.require(manager.get("ActiveState")=="active" and manager.get("SubState")=="running"
                  and manager.get("User")==str(account["uid"]) and manager.get("Delegate")=="yes", "PREPARE_MANAGER_DELEGATION")
        # Only this new user's runtime unit; no global user template or linger.
        runtime=Path("/run/user")/str(account["uid"])
        c.require(runtime.stat().st_uid==account["uid"] and stat.S_ISSOCK((runtime/"systemd/private").stat().st_mode), "PREPARE_USER_MANAGER_TRANSPORT")
        units=runtime/"systemd/user"
        if not units.exists(): create_directory(units,owner=account["uid"],gid=account["gid"])
        unit=units/p["parents"]["ordinary"]["unit"]
        create_file(unit,self.slice_bytes(p["parents"]["ordinary"]),mode=0o644,owner=account["uid"],gid=account["gid"])
        self.user_command([self.tool("systemctl"),"--user","daemon-reload"])
        self.user_command([self.tool("systemctl"),"--user","start",p["parents"]["ordinary"]["unit"]])
        result={}
        for role,parent in p["parents"].items():
            row=self.show(parent["unit"],ordinary=role=="ordinary")
            c.require(row.get("ActiveState")=="active" and row.get("LoadState")=="loaded", "PREPARE_PARENT_INACTIVE")
            group=row.get("ControlGroup",""); c.path(group)
            if role=="ordinary":
                c.require(str(Path(group).parent)==manager["ControlGroup"], "PREPARE_ORDINARY_PARENT")
            else: c.require(group=="/"+parent["unit"], "PREPARE_SYSTEM_PARENT")
            location=Path("/sys/fs/cgroup")/group.lstrip("/")
            info=identity(location.stat(),group)
            controllers=set(kernel(str(location/"cgroup.controllers")).decode().split())
            subtree=set(kernel(str(location/"cgroup.subtree_control")).decode().split())
            c.require({"cpu","memory","pids"}<=controllers, "PREPARE_EFFECTIVE_CONTROLLERS")
            c.require(kernel(str(location/"memory.max")).strip()==str(parent["memory_bytes"]).encode()
                and kernel(str(location/"pids.max")).strip()==str(parent["tasks_max"]).encode()
                and kernel(str(location/"memory.swap.max")).strip()==b"0", "PREPARE_CGROUP_LIMITS")
            quota,period=map(int,kernel(str(location/"cpu.max")).split())
            c.require(quota*1000000==period*parent["cpu_quota_per_sec_usec"], "PREPARE_CPU_LIMIT")
            if role=="ordinary":
                st=(location/"cgroup.procs").stat()
                c.require(st.st_uid==account["uid"] and st.st_mode&0o200, "PREPARE_CGROUP_NOT_DELEGATED")
            info.update(unit=parent["unit"],memory_bytes=parent["memory_bytes"],tasks_max=parent["tasks_max"],
                        cpu_quota_per_sec_usec=parent["cpu_quota_per_sec_usec"])
            result[role]=info
        for name in ("cgroup.controllers","cgroup.subtree_control"):
            available=set(kernel("/sys/fs/cgroup"+manager["ControlGroup"]+"/"+name).decode().split())
            c.require({"cpu","memory","pids"}<=available,"PREPARE_MANAGER_CONTROLLERS")
        result["manager"]={"unit":instance,**manager}
        return result

    @staticmethod
    def slice_bytes(parent):
        percent=parent["cpu_quota_per_sec_usec"]/10000
        return ("[Unit]\nDescription=Local Hand isolated Q2 preparation\nStopWhenUnneeded=no\n[Slice]\n"
                "CPUAccounting=yes\nCPUQuota="+format(percent,"g")+"%\nCPUQuotaPeriodSec=100ms\n"
                "MemoryAccounting=yes\nMemoryMax="+str(parent["memory_bytes"])+"\nMemorySwapMax=0\n"
                "TasksAccounting=yes\nTasksMax="+str(parent["tasks_max"])+"\n").encode()

    def finish(self,result):
        if self.reservation is not None:
            create_file(self.reservation/"preparation-result.json",c.encoded(result))


def prepare(plan, backend=None, *, validate_settings):
    raw=c.encoded(plan); plan=c.decode(raw,sha(raw))
    # Assembly settings receive strict semantic admission before any mutation.
    validate_settings(plan["settings"])
    backend=LinuxBackend(plan) if backend is None else backend
    result=dict(schema=SCHEMA,preparation_id=plan["preparation_id"],plan_sha256=sha(raw),status="BLOCKED",reason=None,
                facts={},q2_accepted=False,q3_accepted=False,production_supported=False,fixture_generated=False)
    reserved=False
    try:
        result["facts"].update(backend.preflight())
        backend.reserve(plan); reserved=True
        for name,operation in (("ordinary",backend.account),("directories",backend.directories),
                               ("installation",backend.install),("roots",backend.roots),("parents",backend.parents)):
            backend.guard(); backend.event("step-intent",{"step":name})
            result["facts"][name]=operation(); backend.event("step-result",{"step":name})
        result["facts"]["retained_after"]=backend.snapshot()
        c.require(result["facts"]["retained_after"]==result["facts"]["retained_before"], "PREPARE_RETAINED_CHANGED")
        result["status"]="RESOURCES_PREPARED"
    except Exception as error:
        reserved = reserved or getattr(backend,"reservation",None) is not None
        result["status"]="INCOMPLETE" if reserved else "BLOCKED"
        result["reason"]=reason(error)
        command_failure=getattr(backend,"last_command_failure",None)
        if command_failure is not None:result["command_failure"]=command_failure
        if reserved and result["reason"] in ("PREPARE_COMMAND_TIMEOUT","PREPARE_DEADLINE","PREPARE_COMMAND_OUTPUT_LIMIT"):
            result["status"]="UNKNOWN"
    backend.finish(result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    # Mutations require the driver, its complete strict settings and one original
    # management delivery. This resource module alone is intentionally inert.
    print(json.dumps(dict(schema=SCHEMA,status="BLOCKED",reason="EXPLICIT_PRIVATE_INPUTS_REQUIRED",
                          q2_accepted=False,q3_accepted=False,production_supported=False,fixture_generated=False)))
    return 3


if __name__=="__main__":
    raise SystemExit(main())
