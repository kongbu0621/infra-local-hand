"""One attested continuation of the known account-parser failure.

This test-only entry preserves the original preparation and candidate. It never
replays group creation and accepts only the exact five-record failure boundary.
The caller supplies the already running guest's absolute recovery deadline.
"""
from __future__ import annotations

import argparse
import errno
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
import time


def sibling(name):
    spec=importlib.util.spec_from_file_location("_recovery_"+name,Path(__file__).with_name(name+".py"))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


p=sibling("q2_prepare")
c=p.c
kernel=p.kernel
read=p.read
sha=p.sha
Quota=p.Quota
SCHEMA="local-hand-q2-preparation-recovery-plan/v1"
RESULT_SCHEMA="local-hand-q2-preparation-recovery/v1"
SCOPE="LH-Q2-PREP-RECOVERY-v1"
BASELINE="72c06ec68d370333f5ffb1079023917828b3e681"
RECORDS=("0001-step-intent.json","0002-command-intent.json","0003-command-result.json",
         "0004-command-intent.json","0005-command-result.json")
PINNED_FILES=("intent.json","preparation-result.json",*RECORDS)
ORIGINAL_FILES=(*PINNED_FILES,"preflight.json")
ERROR=b"configuration error - unknown item 'CREATE_MAIL_SPOOL' (notify administrator)\n"


def decode(raw,digest):
    c.token(digest,c.HEX);c.require(sha(raw)==digest,"RECOVERY_DIGEST")
    r=c.document(raw)
    c.keys(r,("schema","purpose","scope","baseline","recovery_id","preparation_id","plan_sha256",
              "reservation","staged_plan","original_files","original_service","original_capture",
              "recovery_source","retained_inputs"))
    c.require((r["schema"],r["purpose"],r["scope"],r["baseline"])==
              (SCHEMA,"KNOWN_ACCOUNT_PARSE_FAILURE",SCOPE,BASELINE),"RECOVERY_SCOPE")
    for name in ("recovery_id","preparation_id"):c.token(r[name],r"[a-z][a-z0-9]{7,31}")
    c.token(r["plan_sha256"],c.HEX);c.path(r["staged_plan"])
    pin=r["reservation"];c.keys(pin,("path","device","inode","uid","gid","mode"));c.path(pin["path"])
    c.number(pin["device"],1);c.number(pin["inode"],1)
    for key in ("uid","gid","mode"):c.number(pin[key],0)
    c.require((pin["uid"],pin["gid"],pin["mode"])==(0,0,stat.S_IFDIR|0o700),"RECOVERY_RESERVATION_PIN")
    c.keys(r["original_files"],PINNED_FILES)
    for digest in r["original_files"].values():c.token(digest,c.HEX)
    c.require(r["original_files"]["intent.json"]==r["plan_sha256"],"RECOVERY_INTENT_BINDING")
    c.token(r["original_service"],r"lhq[a-z0-9-]{1,100}\.service")
    capture=r["original_capture"]
    c.keys(capture,("report_sha256","stdout_sha256","stderr_sha256","receipt_sha256","returncode","eof","failure"))
    for key in ("report_sha256","stdout_sha256","stderr_sha256","receipt_sha256"):c.token(capture[key],c.HEX)
    c.require(type(capture["returncode"]) is int and capture["returncode"]==3 and capture["eof"]==["stderr","stdout"]
              and capture["failure"] is None and capture["receipt_sha256"]==r["original_files"]["preparation-result.json"],
              "RECOVERY_ORIGINAL_CAPTURE")
    source=r["recovery_source"];c.keys(source,("commit","tree","files"))
    for key in ("commit","tree"):c.token(source[key],r"[0-9a-f]{40}")
    c.require(type(source["files"]) is dict and 4<=len(source["files"])<=64,"RECOVERY_SOURCE_FILES")
    for path,digest in source["files"].items():c.path(path);c.token(digest,c.HEX)
    inputs=r["retained_inputs"]
    c.require(type(inputs) is list and 1<=len(inputs)<=32,"RECOVERY_RETAINED_INPUTS")
    for item in inputs:
        c.keys(item,("path","category"));c.path(item["path"])
        c.require(item["category"] in ("installation","state","journal","capture"),"RECOVERY_COST_CATEGORY")
        c.require(not c.overlap(item["path"],pin["path"]),"RECOVERY_COST_ALIAS")
    c.require(all(not c.overlap(a["path"],b["path"]) for i,a in enumerate(inputs) for b in inputs[i+1:]),"RECOVERY_COST_ALIAS")
    return r


def bind_plan(plan,recovery):
    raw=c.encoded(plan);c.decode(raw,sha(raw));r=decode(c.encoded(recovery),sha(c.encoded(recovery)))
    c.require(r["preparation_id"]==plan["preparation_id"] and r["plan_sha256"]==sha(raw)
              and r["reservation"]["path"]==plan["directories"]["reservation"]["path"],"RECOVERY_PLAN_CHANGED")
    covered=[Path(item["path"]) for item in r["retained_inputs"] if item["category"]=="installation"]
    for value in (plan["candidate"]["source"],plan["candidate"]["wheel"],r["staged_plan"],*r["recovery_source"]["files"]):
        name=Path(value);c.require(any(root==name or root in name.parents for root in covered),"RECOVERY_UNCHARGED_INPUT")
    for item in r["retained_inputs"]:
        for name in ([d["path"] for d in plan["directories"].values()]+[plan["candidate"]["destination"]]
                     +[d["path"] for d in plan["retained"]]):
            c.require(not c.overlap(item["path"],name),"RECOVERY_COST_ALIAS")
    return r


def verify_records(plan,recovery,raw):
    """Pure proof of the one supported command boundary; no execution."""
    c.require(set(raw)==set(ORIGINAL_FILES),"RECOVERY_ORIGINAL_MEMBERS")
    for name,digest in recovery["original_files"].items():
        c.require(sha(raw[name])==digest,"RECOVERY_ORIGINAL_CHANGED")
    c.require(raw["intent.json"]==c.encoded(plan),"RECOVERY_PLAN_CHANGED")
    values={name:c.document(value) for name,value in raw.items()}
    receipt=values["preparation-result.json"]
    c.require(receipt.get("schema")==p.SCHEMA and receipt.get("status")=="INCOMPLETE"
        and receipt.get("reason")=="PREPARE_COMMAND_FAILED" and receipt.get("preparation_id")==plan["preparation_id"]
        and receipt.get("plan_sha256")==recovery["plan_sha256"]
        and all(receipt.get(key) is False for key in ("q2_accepted","q3_accepted","production_supported","fixture_generated")),
        "RECOVERY_ORIGINAL_VERDICT")
    facts=receipt.get("facts")
    c.keys(facts,("host","mounts","retained_before","capacity_observed"))
    c.require(facts["host"]==plan["host"],"RECOVERY_ORIGINAL_HOST")
    c.require(raw["preflight.json"]==c.encoded(facts),"RECOVERY_PREFLIGHT_CHANGED")
    a=plan["account"]
    group=[plan["tools"]["groupadd"]["path"],"--gid",str(a["gid"]),a["name"]]
    user=[plan["tools"]["useradd"]["path"],"--uid",str(a["uid"]),"--gid",str(a["gid"]),
          "--no-user-group","--no-log-init","-K","CREATE_MAIL_SPOOL=no","--no-create-home",
          "--home-dir",plan["directories"]["state"]["path"],"--shell","/usr/sbin/nologin","--password","!",a["name"]]
    expected=[{"step":"ordinary"},{"argv":group},
        dict(argv=group,returncode=0,eof=["stderr","stdout"],failure=None,stdout="",stderr=""),{"argv":user},
        dict(argv=user,returncode=3,eof=["stderr","stdout"],failure=None,stdout="",stderr=ERROR.hex())]
    c.require([values[name] for name in RECORDS]==expected,"RECOVERY_UNSUPPORTED_BOUNDARY")
    return receipt


class RecoveryBackend(p.LinuxBackend):
    def __init__(self,plan,recovery,issued_ns,deadline_ns):
        super().__init__(plan)
        c.number(issued_ns,1);c.number(deadline_ns,issued_ns+1)
        c.require(deadline_ns-issued_ns<=140*10**9 and issued_ns<=time.monotonic_ns()<deadline_ns,"RECOVERY_DEADLINE")
        self.issued_ns=issued_ns;self.deadline=deadline_ns
        self.recovery=bind_plan(plan,recovery);self.recovery_directory=None
        self.original_directory=Path(recovery["reservation"]["path"])
        self.original_hashes={};self.original_receipt=None;self.costs={}

    def guard(self):
        c.require(time.monotonic_ns()<self.deadline,"RECOVERY_DEADLINE")

    def check_account_boundary(self):
        import pwd,grp
        self.guard();a=self.plan["account"]
        for lookup,key in ((pwd.getpwnam,a["name"]),(pwd.getpwuid,a["uid"])):
            try:lookup(key)
            except KeyError:continue
            raise ValueError("RECOVERY_ACCOUNT_EXISTS")
        try:groups=(grp.getgrnam(a["name"]),grp.getgrgid(a["gid"]))
        except KeyError as error:raise ValueError("RECOVERY_GROUP_CHANGED") from error
        for group in groups:
            c.require(group.gr_name==a["name"] and group.gr_gid==a["gid"] and group.gr_mem==[],"RECOVERY_GROUP_CHANGED")
        for filename in ("/etc/shadow","/etc/subuid","/etc/subgid"):
            try:raw=read(filename,c.LIMIT,noatime=True)
            except FileNotFoundError:continue
            c.require(not any(line.split(b":",1)[0]==a["name"].encode() for line in raw.splitlines()),"RECOVERY_ACCOUNT_SIDE_EFFECT")
        groups=read("/etc/group",c.LIMIT,noatime=True)
        c.require(not any(a["name"].encode() in line.split(b":")[-1].split(b",") for line in groups.splitlines()),
                  "RECOVERY_ACCOUNT_SIDE_EFFECT")
        for prefix in ("/var/mail","/var/spool/mail"):
            c.require(not os.path.lexists(prefix+"/"+a["name"]),"RECOVERY_MAIL_EXISTS")

    def original_members(self,*,reserved=False):
        self.guard();fd=p.opened(str(self.original_directory),directory=True)
        try:
            c.require(p.identity(os.fstat(fd),str(self.original_directory))==self.recovery["reservation"],"RECOVERY_RESERVATION_CHANGED")
            expected=set(ORIGINAL_FILES)
            if reserved:expected.add(self.recovery["recovery_id"])
            names=[]
            with os.scandir(fd) as entries:
                for entry in entries:
                    c.require(len(names)<len(expected),"RECOVERY_ORIGINAL_MEMBERS");names.append(entry.name)
            c.require(set(names)==expected and len(names)==len(expected),"RECOVERY_ORIGINAL_MEMBERS")
        finally:os.close(fd)

    def attest_original(self):
        self.original_members()
        raw={name:read(str(self.original_directory/name),c.LIMIT,noatime=True) for name in ORIGINAL_FILES}
        self.original_receipt=verify_records(self.plan,self.recovery,raw)
        self.original_hashes={name:sha(value) for name,value in raw.items()}
        c.require(read(self.recovery["staged_plan"],c.LIMIT,noatime=True)==raw["intent.json"],"RECOVERY_STAGED_PLAN_CHANGED")
        required={str(Path(__file__).with_name(name+".py")) for name in
                  ("q2_prepare_recovery","q2_prepare","q2_prepare_contract","q2_prepare_build")}
        files=self.recovery["recovery_source"]["files"]
        c.require(required<=set(files),"RECOVERY_SOURCE_CLOSURE")
        for name,digest in files.items():
            self.guard();c.require(sha(read(name,c.LIMIT,noatime=True))==digest,"RECOVERY_SOURCE_CHANGED")

    def original_service_stopped(self):
        self.guard()
        unit=self.recovery["original_service"]
        units=self.command([self.tool("systemctl"),"--system","list-units","--all","--plain","--no-legend","--type=service"])
        jobs=self.command([self.tool("systemctl"),"--system","list-jobs","--no-legend"])
        unissued={value["unit"] for value in self.plan["settings"]["controllers"].values()}
        for candidate in unissued:
            for prefix in ("/etc/systemd/system/","/run/systemd/system/","/usr/lib/systemd/system/","/lib/systemd/system/"):
                c.require(not os.path.lexists(prefix+candidate) and not os.path.lexists(prefix+candidate+".d"),
                          "RECOVERY_RUN_ALREADY_ISSUED")
        c.require(not unissued & {line.split()[0] for line in units.decode().splitlines() if line.split()}
                  and all(not unissued & set(line.split()) for line in jobs.decode().splitlines()),"RECOVERY_RUN_ALREADY_ISSUED")
        c.require(all(unit not in line.split() for line in jobs.decode().splitlines()),"RECOVERY_ORIGINAL_SERVICE_ACTIVE")
        if not any(line.split() and line.split()[0]==unit for line in units.decode().splitlines()):return
        output=self.command([self.tool("systemctl"),"--system","show",self.recovery["original_service"],
            "--property=LoadState,ActiveState,SubState,MainPID,ControlPID,Job"])
        rows=dict(line.split("=",1) for line in output.decode().splitlines() if "=" in line)
        c.require(set(rows)=={"LoadState","ActiveState","SubState","MainPID","ControlPID","Job"}
            and rows["LoadState"] in ("loaded","not-found") and rows["ActiveState"] in ("inactive","failed")
            and rows["MainPID"]==rows["ControlPID"]=="0" and rows["Job"] in ("","0"),"RECOVERY_ORIGINAL_SERVICE_ACTIVE")

    def inventory(self,path,*,seen=None):
        """Count each block/inode once, with bounded traversal and no aliases."""
        pending=[Path(path)];seen=set() if seen is None else seen;total=0;count=0;device=None
        while pending:
            self.guard();name=pending.pop();info=name.lstat();key=(info.st_dev,info.st_ino)
            c.require(key not in seen and not stat.S_ISLNK(info.st_mode),"RECOVERY_COST_ALIAS")
            if device is None:device=info.st_dev
            c.require(info.st_dev==device,"RECOVERY_COST_MOUNT_CHANGED")
            seen.add(key);count+=1;total+=max(info.st_size,info.st_blocks*512)
            c.require(count<=32768 and total<=256*1024**2,"RECOVERY_INVENTORY_LIMIT")
            if stat.S_ISDIR(info.st_mode):
                with os.scandir(name) as entries:
                    for entry in entries:
                        c.require(len(pending)+count<32768,"RECOVERY_INVENTORY_LIMIT");pending.append(Path(entry.path))
            else:c.require(stat.S_ISREG(info.st_mode) and info.st_nlink==1,"RECOVERY_COST_TYPE")
        self.guard()
        return {"bytes":total,"inodes":count}

    def measure_costs(self):
        costs={role:dict(bytes=0,inodes=0) for role in ("installation","state","journal","capture")}
        items=list(self.recovery["retained_inputs"])+[{"path":str(self.original_directory),"category":"state"}]
        mapping={"state":"state","authority":"state","journal":"journal","capture":"capture",
                 "declarations":"capture","session":"capture","control":"capture"}
        for role,category in mapping.items():
            name=self.plan["directories"][role]["path"]
            if os.path.lexists(name):items.append(dict(path=name,category=category))
        destination=self.plan["candidate"]["destination"]
        if os.path.lexists(destination):items.append(dict(path=destination,category="installation"))
        seen=set()
        for item in items:
            value=self.inventory(item["path"],seen=seen)
            for key in ("bytes","inodes"):costs[item["category"]][key]+=value[key]
        for role,value in costs.items():
            for key in ("bytes","inodes"):
                c.require(value[key]<=self.plan["budgets"][role+"_"+key],"RECOVERY_TOTAL_CAPACITY")
        return costs

    def verify_preserved(self):
        self.original_members(reserved=self.reservation is not None)
        for name,digest in self.original_hashes.items():
            c.require(sha(read(str(self.original_directory/name),c.LIMIT,noatime=True))==digest,"RECOVERY_ORIGINAL_CHANGED")
        c.require(self.snapshot()==self.original_receipt["facts"]["retained_before"],"RECOVERY_Q1_CHANGED")
        self.costs=self.measure_costs();return True

    def reserve(self,plan):
        self.verify_preserved();self.check_account_boundary()
        path=self.original_directory/self.recovery["recovery_id"]
        value=dict(plan=self.recovery,issued_ns=self.issued_ns,deadline_ns=self.deadline,
                   original_files=self.original_hashes,attestation=self.observed,costs=self.costs)
        raw=c.encoded(value)
        size=((len(raw)+self.log_block-1)//self.log_block)*self.log_block+self.log_block
        c.require(self.log_bytes+size+c.LIMIT<=self.log_byte_limit and self.max_events+4<=self.log_inode_limit,
                  "RECOVERY_LOG_CAPACITY")
        self.recovery_directory=p.create_directory(path);self.reservation=path
        p.create_file(path/"recovery-intent.json",raw);self.log_bytes+=size

    def account(self):
        self.check_account_boundary()
        self.command(self.useradd_argv())
        result=self.verify_account();a=self.plan["account"]
        c.require(not os.path.lexists(self.plan["directories"]["state"]["path"]),"RECOVERY_UNPLANNED_HOME")
        for prefix in ("/var/mail","/var/spool/mail"):
            c.require(not os.path.lexists(prefix+"/"+a["name"]),"RECOVERY_UNPLANNED_MAIL")
        for filename in ("/etc/subuid","/etc/subgid"):
            try:raw=read(filename,c.LIMIT,noatime=True)
            except FileNotFoundError:continue
            c.require(not any(line.split(b":",1)[0]==a["name"].encode() for line in raw.splitlines()),"RECOVERY_UNPLANNED_SUBIDS")
        return result

    def install(self):
        result=super().install()
        installed=self.inventory(self.plan["candidate"]["destination"])
        c.require(installed["bytes"]<=192*1024**2 and installed["inodes"]<=8192,"RECOVERY_INSTALLATION_RESERVE")
        self.costs=self.measure_costs()
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
        self.attest_original()
        self.check_account_boundary()
        account=p["account"]
        self.costs=self.measure_costs()
        self.log_bytes=self.costs["state"]["bytes"]
        self.log_inode_limit-=self.costs["state"]["inodes"]
        c.require(self.costs["installation"]["bytes"]+192*1024**2<=p["budgets"]["installation_bytes"]
                  and self.costs["installation"]["inodes"]+8192<=p["budgets"]["installation_inodes"],
                  "RECOVERY_INSTALLATION_RESERVE")
        for tool in p["tools"].values():
            raw = read(tool["path"], 64*1024**2)
            c.require(raw.startswith(b"\x7fELF") and sha(raw) == tool["sha256"]
                      and os.stat(tool["path"]).st_mode & 0o111, "PREPARE_TOOL_CHANGED")
        for role,filename in (("git","git"),("setpriv","setpriv"),("systemctl","systemctl"),("systemd_run","systemd-run")):
            c.require(p["tools"][role]["path"]==str(Path("/usr/bin",filename).resolve(strict=True)),"PREPARE_FIXED_TOOL_PATH")
        for role,item in p["directories"].items():
            if role!="reservation":self.absent(item["path"],device=p["mounts"][item["filesystem"]]["device"])
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
        self.original_service_stopped()
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
        c.require(self.max_events+4<=self.log_inode_limit and self.log_bytes+estimate<=self.log_byte_limit,"PREPARE_LOG_CAPACITY")
        self.observed = dict(host=actual, mounts=mounts, retained_before=retained,
                             capacity_observed=dict(commitments=commitments, quota_inventory=inventory,
                                 preparation_events=self.max_events,preparation_log_bytes=estimate))
        c.require(retained==self.original_receipt["facts"]["retained_before"],"RECOVERY_Q1_CHANGED")
        return self.observed

    def finish(self,result):
        if self.reservation is not None:
            p.create_file(self.reservation/"recovery-result.json",c.encoded(result))


def recover(plan,recovery,backend=None,*,validate_settings,issued_ns,deadline_ns):
    r=bind_plan(plan,recovery);validate_settings(plan["settings"])
    backend=RecoveryBackend(plan,r,issued_ns,deadline_ns) if backend is None else backend
    result=dict(schema=RESULT_SCHEMA,status="BLOCKED",reason=None,preparation_id=plan["preparation_id"],
                plan_sha256=r["plan_sha256"],facts={},q2_accepted=False,q3_accepted=False,
                production_supported=False,fixture_generated=False)
    try:
        result["facts"].update(backend.preflight());backend.reserve(plan)
        for name,operation in (("ordinary",backend.account),("directories",backend.directories),
                               ("installation",backend.install),("roots",backend.roots),("parents",backend.parents)):
            backend.guard();backend.event("step-intent",{"step":name})
            result["facts"][name]=operation();backend.event("step-result",{"step":name})
        result["facts"]["retained_after"]=backend.snapshot();backend.verify_preserved()
        result["status"]="RESOURCES_RECOVERED"
        result["recovery"]=dict(id=r["recovery_id"],plan_sha256=sha(c.encoded(r)),source=r["recovery_source"],
            original_receipt_sha256=r["original_files"]["preparation-result.json"],directory=backend.recovery_directory,
            issued_ns=issued_ns,deadline_ns=deadline_ns,attested=True,original_files_preserved=True,
            original_files=backend.original_hashes,original_capture=r["original_capture"],costs=backend.costs)
    except Exception as error:
        result["status"]="INCOMPLETE" if backend.reservation is not None else "BLOCKED"
        result["reason"]=p.reason(error)
        if backend.reservation is not None and result["reason"] in ("RECOVERY_DEADLINE","PREPARE_COMMAND_TIMEOUT","PREPARE_COMMAND_OUTPUT_LIMIT"):
            result["status"]="UNKNOWN"
        detail=getattr(backend,"last_command_failure",None)
        if detail is not None:result["command_failure"]=detail
    backend.finish(result);return result


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(dict(schema=RESULT_SCHEMA,status="BLOCKED",reason="EXPLICIT_RECOVERY_PLAN_REQUIRED",q2_accepted=False)))
    return 3


if __name__=="__main__":raise SystemExit(main())
