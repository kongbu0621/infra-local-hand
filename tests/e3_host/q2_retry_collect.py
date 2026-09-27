"""Bounded read-only collection after the one approved Q2 replacement attempt.

The original host window and clock anchor are mandatory. Collection observes
retained bytes and current state only: it never starts/stops a unit, issues a
quota call, touches a ledger through SQLite, or repairs missing original EOF.
No arguments create no files or processes. The sole result is bounded stdout.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import signal
import stat
import subprocess
import sys
import time

SCHEMA = "local-hand-q2-cpuquota-retry-collection/v1"
BUNDLE_SCHEMA = "local-hand-q2-cpuquota-retry-evidence-bundle/v1"
MAX_RAW = 16 * 1024**2
MAX_ENTRIES = 4096
FILE_LIMIT = 256 * 1024
LARGE_NAMES = frozenset(("manifest.json", "handoff.json", "retry-preparation.json", "retry-intent.json", "prepared.json", "retry.json"))
OUTPUT_LIMIT = 2 * 1024**2
NS = 10**9
PROPERTIES = ("Id", "LoadState", "ActiveState", "SubState", "MainPID", "ControlPID", "ControlGroup",
              "InvocationID", "Job", "Result", "ExecMainCode", "ExecMainStatus", "User")


def require(ok, code):
    if not ok: raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def helper(name):
    spec = importlib.util.spec_from_file_location("_retry_collect_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "COLLECT_DUPLICATE_KEY"); result[key] = value
        return result
    def rejected(_): raise ValueError("COLLECT_JSON_NUMBER")
    value = json.loads(raw, object_pairs_hook=pairs, parse_float=rejected, parse_constant=rejected)
    require(type(value) is dict, "COLLECT_DOCUMENT")
    return value


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, mode=info.st_mode, uid=info.st_uid, gid=info.st_gid,
                size=info.st_size, allocated_bytes=info.st_blocks*512, nlink=info.st_nlink,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns)


def absolute(path):
    require(type(path) is str and path.startswith("/") and not path.startswith("//")
            and str(PurePosixPath(path)) == path and ".." not in PurePosixPath(path).parts and path != "/",
            "COLLECT_PATH")
    return path


class Reader:
    """No-follow finite reads beneath an already selected trust root.

    Production selects '/'. Tests may select a temporary directory as their
    trust root; this does not change the production CLI's path/protection checks.
    """
    def __init__(self, guard, *, uids=(0,), root="/", max_raw=MAX_RAW, max_entries=MAX_ENTRIES):
        self.guard = guard; self.uids = set(uids); self.root = str(Path(root))
        self.max_raw = max_raw; self.max_entries = max_entries
        self.total = 0; self.seen = {}; self.raw = {}
        self.fd = os.open(self.root, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NOATIME)
        info = os.fstat(self.fd)
        require(info.st_uid in self.uids and not info.st_mode & 0o022, "COLLECT_ROOT_PROTECTION")

    def close(self):
        os.close(self.fd)

    def opened(self, path, *, directory=False):
        self.guard(); absolute(path)
        relative = PurePosixPath(path).relative_to(self.root)
        require(relative.parts, "COLLECT_ROOT_OBJECT")
        fd = os.dup(self.fd)
        try:
            for index, part in enumerate(relative.parts):
                folder = directory or index < len(relative.parts)-1
                child = os.open(part, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC|os.O_NOATIME|
                                (os.O_DIRECTORY if folder else 0), dir_fd=fd)
                os.close(fd); fd = child
                info = os.fstat(fd)
                require(info.st_uid in self.uids and not info.st_mode & 0o6022, "COLLECT_PROTECTION")
                require(stat.S_ISDIR(info.st_mode) if folder else stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                        "COLLECT_OBJECT_TYPE")
            return fd
        except BaseException:
            os.close(fd); raise

    def read(self, path, *, limit=FILE_LIMIT, virtual=False):
        path = str(path)
        if not virtual and path in self.raw:
            return self.raw[path]
        fd = self.opened(path)
        try:
            before = identity(os.fstat(fd))
            require(before["size"] <= limit, "COLLECT_FILE_LIMIT")
            require(path in self.seen or len(self.seen) < self.max_entries, "COLLECT_ENTRY_LIMIT")
            raw = bytearray()
            while len(raw) <= limit:
                self.guard(); block = os.read(fd, min(65536, limit+1-len(raw)))
                if not block: break
                raw.extend(block)
                require(self.total + len(raw) <= self.max_raw, "COLLECT_TOTAL_LIMIT")
            require(len(raw) <= limit and (virtual or len(raw) == before["size"]), "COLLECT_FILE_LIMIT")
            require(identity(os.fstat(fd)) == before, "COLLECT_FILE_CHANGED")
            self.total += len(raw)
            if not virtual:
                self.seen[path] = before; self.raw[path] = bytes(raw)
            return bytes(raw)
        finally:
            os.close(fd)

    def tree(self, path):
        path = str(path); queue = [path]; entries = []
        while queue:
            self.guard(); current = queue.pop()
            fd = self.opened(current, directory=True)
            try:
                before = identity(os.fstat(fd)); self.seen[current] = before
                require(len(self.seen) <= self.max_entries, "COLLECT_ENTRY_LIMIT")
                entries.append(dict(path=current, kind="directory", identity=before))
                with os.scandir(fd) as iterator:
                    names = []
                    for item in iterator:
                        require(len(self.seen)+len(queue)+len(names) < self.max_entries, "COLLECT_ENTRY_LIMIT")
                        names.append(item.name)
                for name in sorted(names):
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    child = str(PurePosixPath(current)/name)
                    if stat.S_ISDIR(info.st_mode):
                        queue.append(child)
                    else:
                        require(stat.S_ISREG(info.st_mode), "COLLECT_OBJECT_TYPE")
                        limit = 2*1024**2 if name in LARGE_NAMES else FILE_LIMIT
                        raw = self.read(child, limit=limit)
                        entries.append(dict(path=child, kind="file", identity=self.seen[child],
                                            sha256=sha(raw), content_base64=base64.b64encode(raw).decode()))
                require(identity(os.fstat(fd)) == before, "COLLECT_DIRECTORY_CHANGED")
            finally:
                os.close(fd)
        return entries

    def stable(self):
        for path, expected in self.seen.items():
            self.guard(); fd = self.opened(path, directory=stat.S_ISDIR(expected["mode"]))
            try:
                require(identity(os.fstat(fd)) == expected, "COLLECT_OBSERVED_OBJECT_CHANGED")
            finally:
                os.close(fd)


def fixed_envelope(anchor, envelope, attempt_id, *, boot_id, now_ns, anchor_sha256=None):
    d = helper("q2_retry_delivery")
    d.keys(envelope,d.ENVELOPE_FIELDS);d.token(attempt_id);d.boot(boot_id)
    require(envelope["schema"]==d.ENVELOPE_SCHEMA and envelope["attempt_id"]==attempt_id
            and envelope["boot_id"]==boot_id,"COLLECT_ENVELOPE_CHANGED")
    for key in ("issued_ns","deadline_ns","preparation_deadline_ns","stop_ns","guest_outer_deadline_ns"):
        d.number(envelope[key],1)
    require(envelope["issued_ns"]<envelope["deadline_ns"]<=envelope["issued_ns"]+d.GUEST_NS
            and envelope["deadline_ns"]+10*NS<=envelope["guest_outer_deadline_ns"]<=envelope["issued_ns"]+d.HOST_NS
            and envelope["stop_ns"]==d.STOP_NS
            and envelope["issued_ns"]<envelope["preparation_deadline_ns"]<=envelope["issued_ns"]+d.PREPARATION_NS
            and envelope["preparation_deadline_ns"]+d.OWNER_NS+d.STOP_NS+d.FINALIZATION_NS<=envelope["deadline_ns"],
            "COLLECT_ENVELOPE_BUDGET")
    if anchor is not None:
        d.validate_clock_anchor(anchor)
        require(d.guest_envelope(anchor, attempt_id=attempt_id, guest_boot_id=boot_id,
                                guest_now_ns=envelope["issued_ns"]) == envelope, "COLLECT_ENVELOPE_CHANGED")
        expected=d.sha(d.encoded(anchor))
        require(anchor_sha256 is None or anchor_sha256==expected,"COLLECT_ANCHOR_DIGEST")
    else:
        require(type(anchor_sha256) is str and re.fullmatch(r"[0-9a-f]{64}",anchor_sha256),"COLLECT_ANCHOR_DIGEST")
        require(envelope["clock_anchor_sha256"]==anchor_sha256,"COLLECT_ANCHOR_DIGEST")
    require(type(now_ns) is int
            and envelope["issued_ns"] <= now_ns < envelope["guest_outer_deadline_ns"] - 2*NS,
            "COLLECT_ORIGINAL_WINDOW_EXPIRED")
    return envelope["guest_outer_deadline_ns"] - 2*NS


def command(argv, *, guard, deadline_ns, env=None, output_limit=32768):
    """Finite read-only systemctl capture in memory, charged to the same bound."""
    guard(); require(type(argv) is list and 0 < len(argv) <= 32, "COLLECT_COMMAND")
    require(all(type(arg) is str and 0 < len(arg) <= 4096 and "\0" not in arg for arg in argv), "COLLECT_COMMAND")
    end = min(deadline_ns, time.clock_gettime_ns(time.CLOCK_BOOTTIME)+2*NS)
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            close_fds=True, start_new_session=True, env=env)
    selector = selectors.DefaultSelector(); streams={"stdout":bytearray(),"stderr":bytearray()};eof=set();error=None
    try:
        for name in streams:
            stream=getattr(proc,name);os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
        while len(eof)!=2 or proc.poll() is None:
            guard()
            left=end-time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            if left <= 50_000_000: error="COLLECT_COMMAND_TIMEOUT";break
            for key,_ in selector.select(min(0.02,left/NS)):
                block=os.read(key.fd,65536)
                if not block:eof.add(key.data);selector.unregister(key.fileobj);continue
                room=output_limit-sum(map(len,streams.values()));streams[key.data].extend(block[:room])
                if len(block)>room:error="COLLECT_COMMAND_OUTPUT_LIMIT";break
            if error:break
    except Exception as failure:
        error=type(failure).__name__+":"+str(failure)[:100]
    finally:
        if error or proc.poll() is None:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        try:proc.wait(timeout=max(0,min(0.05,(end-time.clock_gettime_ns(time.CLOCK_BOOTTIME))/NS)))
        except subprocess.TimeoutExpired:error=error or "COLLECT_COMMAND_EXIT_UNPROVEN"
        selector.close();proc.stdout.close();proc.stderr.close()
    return dict(argv=argv,returncode=proc.returncode,eof=sorted(eof),error=error,
                stdout_base64=base64.b64encode(streams["stdout"]).decode(),
                stderr_base64=base64.b64encode(streams["stderr"]).decode(),
                complete=proc.returncode is not None and eof=={"stdout","stderr"} and error is None)


def rows(record):
    require(record["complete"] and record["returncode"] == 0 and record["stderr_base64"] == "", "COLLECT_SERVICE_CAPTURE")
    text=base64.b64decode(record["stdout_base64"],validate=True).decode("utf-8")
    result={}
    for group in text.strip().split("\n\n"):
        row={}
        for line in group.splitlines():
            key,sep,value=line.partition("=")
            require(sep and key in PROPERTIES and key not in row,"COLLECT_SERVICE_PROPERTIES");row[key]=value
        require(row.get("Id") and row["Id"] not in result,"COLLECT_SERVICE_IDENTITIES");result[row["Id"]]=row
    return result


def observe_runtime(plan, retry, reader, deadline_ns):
    tool=plan["tools"]["systemctl"]["path"]
    # Hashes were pinned in the original plan; don't execute a replaced tool.
    require(sha(reader.read(tool,limit=16*1024**2))==plan["tools"]["systemctl"]["sha256"],"COLLECT_SYSTEMCTL_CHANGED")
    units=[retry["service"],*[item["unit"] for item in retry["settings"]["controllers"].values()],
           *[item["unit"] for role,item in plan["parents"].items() if role!="ordinary"]]
    record=command([tool,"--system","--no-pager","--no-ask-password","show",*units,
                    "--property="+",".join(PROPERTIES)],guard=reader.guard,deadline_ns=deadline_ns,
                   env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C","LC_ALL":"C","SYSTEMD_PAGER":""})
    facts={"system_capture":record,"system_units":{},"parents":{},"new_runtime_services_stopped":False,
           "parent_trees_empty":False}
    facts["system_units"]=rows(record)
    require(set(facts["system_units"])==set(units),"COLLECT_SERVICE_SET")
    stopped=[]
    for name in units[:3]:
        row=facts["system_units"][name]
        stopped.append(row.get("MainPID")=="0" and row.get("ControlPID")=="0" and row.get("Job") in ("","0")
                       and row.get("ActiveState") in ("inactive","failed")
                       and row.get("ControlGroup","")=="")
    facts["new_runtime_services_stopped"]=all(stopped)
    for role,parent in plan["parents"].items():
        fallback=("/user.slice/user-"+str(plan["account"]["uid"])+".slice/user@"+str(plan["account"]["uid"])+".service/"
               if role=="ordinary" else "/")+parent["unit"]
        pin=plan.get("_prepared_parents",{}).get(role)
        group=pin["path"] if pin is not None else fallback
        path="/sys/fs/cgroup"+group
        row={"path":path,"unit":parent["unit"],"exists":False,"empty":False}
        try:
            fd=reader.opened(path,directory=True)
            try:row.update(exists=True,identity=identity(os.fstat(fd)))
            finally:os.close(fd)
            if pin is not None:
                row["same_prepared_identity"]=all(row["identity"][key]==pin[key] for key in ("device","inode"))
            events=reader.read(path+"/cgroup.events",limit=4096,virtual=True).decode()
            parsed=dict(line.split() for line in events.splitlines())
            row.update(events=parsed,empty=parsed.get("populated")=="0")
        except FileNotFoundError:
            row["empty"]=True
            row["absence_scope"]="CURRENT_PATH_ABSENT; NO_ORIGINAL_EXIT_PROOF"
        facts["parents"][role]=row
    facts["parent_trees_empty"]=all(value["empty"] for value in facts["parents"].values())
    return facts


def bundle_report(value, *, output_limit):
    require(type(output_limit) is int and 16384 <= output_limit <= OUTPUT_LIMIT,"COLLECT_OUTPUT_LIMIT")
    def package(data):
        raw=encoded(data);compressed=gzip.compress(raw,compresslevel=6,mtime=0)
        return dict(format="gzip+base64",raw_bytes=len(raw),compressed_bytes=len(compressed),
                    raw_sha256=sha(raw),sha256=sha(compressed),data=base64.b64encode(compressed).decode())
    report=dict(schema=SCHEMA,status="COLLECTED" if value.get("complete") is True else "INCOMPLETE",
                attempt_id=value.get("attempt_id"),reason=value.get("reason"),
                old_files_preserved=value.get("old_files_preserved",False),
                old_ledger_preserved=value.get("old_ledger_preserved",False),
                old_trees_preserved=value.get("old_trees_preserved",False),
                q1_records_preserved=value.get("q1_records_preserved",False),
                remote_stop_proven=False,original_eof_proven=False,q2_accepted=False,q3_accepted=False,
                production_supported=False,bundle=package(value))
    if len(encoded(report))>output_limit:
        # Keep every digest/metadata/error, explicitly omit content, and retain
        # an INCOMPLETE outcome. Never silently truncate a forensic artifact.
        for entry in value.get("files",[]):
            if "content_base64" in entry:
                entry.pop("content_base64");entry["content_omitted"]="WIRE_OUTPUT_LIMIT"
        value["complete"]=False;value["reason"]="COLLECT_WIRE_CONTENT_LIMIT"
        report.update(status="INCOMPLETE",reason=value["reason"],bundle=package(value))
    if len(encoded(report))>output_limit:
        report.pop("bundle");report.update(status="INCOMPLETE",reason="COLLECT_WIRE_METADATA_LIMIT")
    require(len(encoded(report))<=output_limit,"COLLECT_OUTPUT_LIMIT")
    return report


def preserve_snapshots(original, receipt, guard):
    """Read-only resnapshot under the caller's original remaining deadline.

    Hash-only old tree reads are not copied into the 16 MiB evidence payload.
    Existing preparation byte/entry bounds still apply to this independent read.
    """
    backend=helper("q2_retry")
    expected=receipt["retry"]["attestation"]["old_snapshots"]
    require(type(expected) is list and 1<=len(expected)<=128,"COLLECT_OLD_SNAPSHOT_SET")
    require(sum(item["bytes"] for item in expected)<=416*1024**2
            and sum(item["inodes"] for item in expected)<=32768,"COLLECT_OLD_SNAPSHOT_LIMIT")
    observed=[backend.snapshot_tree(item["path"],guard,maximum_bytes=item["bytes"],maximum_entries=item["inodes"])
              for item in expected]
    # Reproduce the old Q1 snapshot format while opening directories with
    # O_NOATIME too. No preparation backend is instantiated by this collector.
    q1=[];total=0;count=0
    for selected in original["retained"]:
        guard();info=os.lstat(selected["path"])
        require(stat.S_ISDIR(info.st_mode) and (info.st_dev,info.st_ino)==(selected["device"],selected["inode"]),
                "COLLECT_Q1_ROOT_IDENTITY")
        pending=[Path(selected["path"])];files=[]
        while pending:
            guard();path=pending.pop();info=path.lstat();count+=1
            require(count<=original["budgets"]["retained_scan_entries"] and not stat.S_ISLNK(info.st_mode)
                    and info.st_dev==selected["device"],"COLLECT_Q1_TREE_LIMIT")
            row=backend.p.identity(info,path)
            if stat.S_ISDIR(info.st_mode):
                fd=backend.p.opened(str(path),directory=True,owner=info.st_uid,noatime=True)
                try:
                    with os.scandir(fd) as entries:
                        for item in entries:
                            require(len(pending)+count<original["budgets"]["retained_scan_entries"],"COLLECT_Q1_TREE_LIMIT")
                            pending.append(path/item.name)
                finally:os.close(fd)
            else:
                require(stat.S_ISREG(info.st_mode) and info.st_nlink==1,"COLLECT_Q1_FILE_TYPE")
                total+=info.st_size
                require(total<=original["budgets"]["retained_scan_bytes"],"COLLECT_Q1_BYTE_LIMIT")
                row.update(size=info.st_size,sha256=backend.p.sha(backend.p.read(path,info.st_size,owner=info.st_uid,noatime=True)))
            files.append(row)
        q1.append(dict(root=selected,entries=len(files),sha256=backend.p.sha(backend.c.encoded(sorted(files,key=lambda row:row["path"])))))
    return dict(old_trees_preserved=observed==expected,old_snapshots=observed,
                q1_records_preserved=q1==receipt["facts"]["retained_before"],q1_snapshots=q1)


def collect(retry, original, envelope, anchor, *, guard, reader, deadline_ns, runtime_observer=observe_runtime,
            preservation_observer=preserve_snapshots):
    value=dict(schema=BUNDLE_SCHEMA,attempt_id=retry["attempt_id"],retry_sha256=sha(encoded(retry)),
               source=retry["source"],candidate=retry["candidate"],clock_anchor=anchor,delivery=envelope,
               old_files_preserved=False,old_ledger_preserved=False,files=[],old_files=[],roots=[],errors=[],
               complete=False,reason=None,q2_accepted=False,q3_accepted=False,production_supported=False)
    def attempt(label,operation):
        try:return operation()
        except Exception as error:
            value["errors"].append(dict(stage=label,type=type(error).__name__,reason=str(error)[:180]));return None
    for path,digest in sorted(retry["old_files"].items()):
        raw=attempt("old-file:"+path,lambda path=path:reader.read(path,limit=2*1024**2))
        value["old_files"].append(dict(path=path,expected_sha256=digest,sha256=sha(raw) if raw is not None else None,
                                        preserved=raw is not None and sha(raw)==digest))
    value["old_files_preserved"]=all(item["preserved"] for item in value["old_files"])
    # Original roots may now contain this new operation's output. Record only
    # their identities/member names; never claim they remain unused after a run.
    for root in original["roots"]:
        def root_observation(root=root):
            fd=reader.opened(root["path"],directory=True)
            try:
                names=[]
                with os.scandir(fd) as entries:
                    for item in entries:
                        require(len(names)<128,"COLLECT_ROOT_MEMBERS");names.append(item.name)
                return dict(path=root["path"],project_id=root["project_id"],identity=identity(os.fstat(fd)),members=sorted(names))
            finally:os.close(fd)
        observed=attempt("quota-root:"+root["path"],root_observation)
        if observed:value["roots"].append(observed)
    for role in ("reservation","authority","state","capture","declarations","journal"):
        path=retry["directories"][role]["path"]
        try:
            entries=reader.tree(path)
            value["files"].extend(dict(role=role,**entry) for entry in entries)
        except FileNotFoundError:
            value["files"].append(dict(role=role,path=path,kind="missing"))
        except Exception as error:
            value["errors"].append(dict(stage="new-tree:"+role,type=type(error).__name__,reason=str(error)[:180]))
    # The preparation receipt pins the old ledger digest at live attestation.
    receipt_path=retry["directories"]["reservation"]["path"]+"/retry-preparation.json"
    def checked_receipt():
        result=decode(reader.read(receipt_path,limit=2*1024**2))
        require(result.get("schema")=="local-hand-q2-cpuquota-retry-preparation/v1"
                and result.get("status")=="RETRY_RESOURCES_PREPARED"
                and result.get("attempt_id")==retry["attempt_id"]
                and result.get("retry_sha256")==sha(encoded(retry))
                and all(result.get(key) is False for key in ("q2_accepted","q3_accepted","production_supported","fixture_generated")),
                "COLLECT_RECEIPT_BINDING")
        attest=result["retry"]["attestation"]
        require(sha(encoded(attest))==result["retry"]["attestation_sha256"]
                and attest.get("old_prepared_sha256")==retry["old_files"][retry["old_prepared"]]
                and all(attest.get(key) is True for key in ("original_owner_issued","unused_roots","unused_ledger")),
                "COLLECT_ATTESTATION_BINDING")
        return result
    receipt=attempt("retry-receipt",checked_receipt)
    if receipt:
        attest=receipt.get("retry",{}).get("attestation",{})
        value["old_ledger_attestation"]=attest.get("ledger")
        ledger=attempt("old-ledger",lambda:reader.read(retry["old_ledger"]["path"],limit=2*1024**2))
        expected=attest.get("ledger",{}).get("sha256")
        value["old_ledger_sha256"]=sha(ledger) if ledger is not None else None
        pin=retry["old_ledger"];observed=reader.seen.get(pin["path"],{})
        value["old_ledger_preserved"]=(type(expected) is str and ledger is not None and sha(ledger)==expected
            and all(observed.get(key)==pin[key] for key in ("device","inode","uid"))
            and stat.S_IMODE(observed.get("mode",0))==pin["mode"])
        preservation=attempt("retained-tree-preservation",lambda:preservation_observer(original,receipt,guard))
        if preservation:value.update(preservation)
    runtime_plan=dict(original)
    if receipt:runtime_plan["_prepared_parents"]=receipt.get("facts",{}).get("parents",{})
    value["runtime"]=attempt("runtime-observation",lambda:runtime_observer(runtime_plan,retry,reader,deadline_ns))
    attempt("stable-read-set",reader.stable)
    value["raw_bytes_read"]=reader.total;value["entries_read"]=len(reader.seen)
    value["complete"]=not value["errors"] and all(value.get(key) is True for key in
        ("old_files_preserved","old_ledger_preserved","old_trees_preserved","q1_records_preserved"))
    value["reason"]=None if value["complete"] else "COLLECTION_OR_PRESERVATION_INCOMPLETE"
    value["scope"]="RETAINED_BYTES_AND_CURRENT_STATE_ONLY; NO_REPLAY_OR_RETROSPECTIVE_EOF"
    return value


def main(argv=None):
    first=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("retry","sha256","clock-anchor","clock-anchor-sha256","delivery-envelope","delivery-sha256"):
        parser.add_argument("--"+name)
    parser.add_argument("--output-limit",type=int,default=OUTPUT_LIMIT)
    args=parser.parse_args(argv)
    reader=None;value=None
    try:
        require(all(getattr(args,key) for key in ("retry","sha256","clock_anchor_sha256","delivery_envelope"))
                and (args.clock_anchor or args.delivery_sha256),
                "EXPLICIT_ORIGINAL_RETRY_WINDOW_REQUIRED")
        require(sys.flags.isolated and sys.dont_write_bytecode and os.getuid()==os.geteuid()==0,
                "COLLECT_ISOLATED_ROOT_REQUIRED")
        # Bootstrap read bound is only a stricter local cap. The validated
        # anchor immediately replaces it with the original absolute deadline.
        bound=[first+2*NS]
        guard=lambda:require(time.clock_gettime_ns(time.CLOCK_BOOTTIME)<bound[0],"COLLECT_ORIGINAL_WINDOW_EXPIRED")
        reader=Reader(guard)
        anchor=None
        if args.clock_anchor:
            anchor_raw=reader.read(args.clock_anchor,limit=16384)
            require(sha(anchor_raw)==args.clock_anchor_sha256,"COLLECT_ANCHOR_DIGEST")
            anchor=decode(anchor_raw)
        envelope_raw=reader.read(args.delivery_envelope,limit=16384)
        require(args.delivery_sha256 is None or sha(envelope_raw)==args.delivery_sha256,"COLLECT_DELIVERY_DIGEST")
        envelope=decode(envelope_raw)
        boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        contract=helper("q2_retry_contract")
        retry=contract.decode(reader.read(args.retry,limit=2*1024**2),args.sha256)
        bound[0]=fixed_envelope(anchor,envelope,retry["attempt_id"],boot_id=boot_id,
                                now_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),anchor_sha256=args.clock_anchor_sha256)
        guard()
        original=helper("q2_prepare_contract").decode(reader.read(retry["original_plan_path"],limit=2*1024**2),
                                                      retry["original_plan_sha256"])
        contract.bind(original,retry)
        reader.uids.add(original["account"]["uid"])
        # Verify the staged source set before running collector helper logic.
        for path,digest in retry["source"]["files"].items():
            require(sha(reader.read(path,limit=2*1024**2))==digest,"COLLECT_SOURCE_CHANGED")
        require(str(Path(__file__).resolve()) in retry["source"]["files"],"COLLECT_SOURCE_NOT_PINNED")
        value=collect(retry,original,envelope,anchor,guard=guard,reader=reader,deadline_ns=bound[0])
        guard();value["finished_boottime_ns"]=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        report=bundle_report(value,output_limit=args.output_limit)
        guard();print(encoded(report).decode(),end="",flush=True)
        return 0 if report["status"]=="COLLECTED" else 3
    except Exception as error:
        report=dict(schema=SCHEMA,status="BLOCKED" if not args.retry else "INCOMPLETE",type=type(error).__name__,
                    reason=str(error)[:180],read_only=True,replay_allowed=False,
                    q2_accepted=False,q3_accepted=False,production_supported=False)
        print(encoded(report).decode(),end="",flush=True)
        return 3
    finally:
        if reader is not None:reader.close()


if __name__=="__main__":raise SystemExit(main())
