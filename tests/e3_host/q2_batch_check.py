"""One explicit, read-only fixture check. Never discovered as a host test.

Usage: python -I -B tests/e3_host/q2_batch_check.py --fixture PATH --sha256 SHA
No fixture yields BLOCKED. This is Q2 assembly preflight, not Q3 execution.
No account, filesystem, quota, socket, service or journal is created here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

SCHEMA = "local-hand-q2-fixture/v1"
LIMIT = 131072


def protected(path, limit):
    spelling = str(path)
    path = Path(path)
    if not path.is_absolute() or str(path) != spelling or ".." in path.parts:
        raise ValueError("FIXTURE_PATH")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for i, part in enumerate(path.parts[1:]):
            flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
            if i < len(path.parts) - 2:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd); fd = child
            info = os.fstat(fd)
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError("FIXTURE_PROTECTION")
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise ValueError("FIXTURE_FILE")
        data = bytearray()
        while len(data) <= limit:
            raw = os.read(fd, min(8192, limit + 1 - len(data)))
            if not raw:break
            data.extend(raw)
        after = os.fstat(fd)
        if len(data) > limit or any(getattr(before,k)!=getattr(after,k) for k in
                                  ("st_dev","st_ino","st_size","st_mtime_ns","st_ctime_ns")):
            raise ValueError("FIXTURE_CHANGED")
        return bytes(data)
    finally:
        os.close(fd)


def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError("DUPLICATE_FIXTURE_KEY")
        result[key]=value
    return result


def decode(raw, digest):
    if len(raw)>LIMIT or type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}",digest) or hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError("FIXTURE_DIGEST")
    value=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _: (_ for _ in ()).throw(ValueError("FIXTURE_NUMBER")))
    if (type(value) is not dict or set(value)!={"schema","purpose","source_commit","files","observer","ordinary","controller_envelope","management_record"}
            or value["schema"]!=SCHEMA or value["purpose"]!="ISOLATED_Q2_CHECK"):
        raise ValueError("FIXTURE_SCHEMA")
    if type(value["source_commit"]) is not str or not re.fullmatch(r"[0-9a-f]{40}",value["source_commit"]):raise ValueError("FIXTURE_SOURCE")
    files=value["files"]
    if type(files) is not dict or not 1<=len(files)<=512:raise ValueError("FIXTURE_FILES")
    for name,checksum in files.items():
        if type(name) is not str or type(checksum) is not str or not re.fullmatch(r"(?:tools|tests/e3_host)/(?:[a-z_][a-z0-9_]*/)*[a-z_][a-z0-9_]*\.py",name) or not re.fullmatch(r"[0-9a-f]{64}",checksum):
            raise ValueError("FIXTURE_FILE_NAME")
    return value


def check(value, repository):
    """All independent host checks in one report; errors never become PASS."""
    results=[]
    def probe(name, action):
        try:action();results.append(dict(check=name,status="PASS"))
        except (OSError,ValueError,RuntimeError) as error:
            results.append(dict(check=name,status="BLOCKED",reason=type(error).__name__+":"+str(error)))
    def required(ok,reason):
        if not ok:raise ValueError(reason)
    required("tests/e3_host/q2_batch_check.py" in value["files"],"HARNESS_PIN_MISSING")
    for name, checksum in value["files"].items():
        required(hashlib.sha256(protected(str(repository/name),2*1024*1024)).hexdigest()==checksum,"SOURCE_BYTES_CHANGED")
    # Every Python module in these runtime packages must be explicitly pinned.
    for folder in ("admin/local_hand_quota_observer","local_hand_jobs","local_hand"):
        for file in (repository/"tools"/folder).glob("**/*.py"):
            required(str(file.relative_to(repository)) in value["files"],"SOURCE_PIN_MISSING")
    sys.path.insert(0,str(repository/"tools"))
    from local_hand_jobs import quota_contract as q
    from local_hand import provenance
    from local_hand.protocol import LocalHandError
    from admin.local_hand_quota_observer import q2_config as c, q2_management as management
    from admin.local_hand_quota_observer.systemd_runtime import boottime_ns
    q._keys(value["observer"],{"path","sha256"})
    config=c.load(value["observer"]["path"],value["observer"]["sha256"])
    data=config.data();grant=config.active().as_dict()
    required(data["source_commit"]==value["source_commit"] and data["tools_path"]==str(repository/"tools"),"OBSERVER_SOURCE_BINDING")
    try:
        candidate = provenance.source_commit(require_clean=True)
    except LocalHandError as error:
        raise ValueError("CANDIDATE_IDENTITY:" + str(error)) from error
    required(candidate==value["source_commit"],"CANDIDATE_IDENTITY")
    required(all(value["files"].get("tools/"+name)==checksum for name,checksum in data["package_files"].items()),"OBSERVER_PACKAGE_BINDING")
    q._keys(value["ordinary"],{"uid","gid","parent"})
    ordinary=value["ordinary"]
    q.integer(ordinary["uid"],1);q.integer(ordinary["gid"],1);c.identity(ordinary["parent"])
    work=next(root for root in grant["roots"] if root["role"]=="work")
    required((ordinary["uid"],ordinary["gid"])==(work["uid"],work["gid"]) and
             ordinary["parent"]==data["peers"][grant["request"]["request_id"]]["parent"],"ORDINARY_BINDING")
    c.identity(value["management_record"])
    record=value["management_record"]
    forbidden=[data["journal"]["path"],data["session"]["path"],data["evidence"]["path"],data["tools_path"],
               config.path,data["service"]["control_path"],grant["endpoint"]["path"],*grant["allocation"]["paths"]]
    required(all(not c.overlap(record["path"],path) for path in forbidden),"RECORD_GEOMETRY")
    probe("systemd_pid1",lambda:required(Path("/proc/1/comm").read_text().strip()=="systemd","SYSTEMD_REQUIRED"))
    probe("administrator",lambda:required(os.getuid()==os.geteuid()==0,"ADMINISTRATOR_REQUIRED"))
    probe("same_boot",lambda:required(Path("/proc/sys/kernel/random/boot_id").read_text().strip()==grant["request"]["boot_id"],"BOOT_CHANGED"))
    probe("original_deadline",lambda:required(grant["management"]["issued_ns"]<=boottime_ns()<grant["request"]["deadline_ns"],"ORIGINAL_DEADLINE"))
    from local_hand_jobs.quota_lifecycle import parent
    for name,pin in (("ordinary",ordinary["parent"]),("query",grant["query_parent"]),("management",grant["management_parent"])):
        probe(name+"_parent",lambda pin=pin:required(parent("/sys/fs/cgroup"+pin["path"],pin)[1],"PARENT_OCCUPIED"))
    def record_check():
        raw=protected(record["path"],65536);info=os.stat(record["path"],follow_symlinks=False)
        required(not raw and (info.st_dev,info.st_ino)==(record["device"],record["inode"]) and
                 stat.S_IMODE(info.st_mode)==0o600,"MANAGEMENT_RECORD_CONSUMED")
    probe("original_empty_record",record_check)
    if all(row["status"]=="PASS" for row in results if row["check"] in ("systemd_pid1","administrator","same_boot")):
        probe("independent_controller",lambda:management.controller(config,value["controller_envelope"]))
    else:results.append(dict(check="independent_controller",status="BLOCKED",reason="HOST_PREREQUISITES"))
    return dict(schema="local-hand-q2-batch-check/v1",status="CHECKED" if all(x["status"]=="PASS" for x in results) else "BLOCKED",
                source_commit=value["source_commit"],request_digest=config.active().request.digest,checks=results,
                q2_accepted=False,q3_status="NOT_RUN",production_supported=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture");parser.add_argument("--sha256")
    args=parser.parse_args(argv)
    result=dict(schema="local-hand-q2-batch-check/v1",status="BLOCKED",q2_accepted=False,q3_status="NOT_RUN",production_supported=False)
    try:
        if not args.fixture or not args.sha256:raise ValueError("EXPLICIT_PRIVATE_FIXTURE_REQUIRED")
        value=decode(protected(args.fixture,LIMIT),args.sha256)
        result=check(value,Path(__file__).resolve().parents[2])
    except (OSError,ValueError,RuntimeError) as error:result["reason"]=type(error).__name__+":"+str(error)
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
    return 0 if result["status"]=="CHECKED" else 3


if __name__=="__main__":raise SystemExit(main())
