"""Create-only installation bindings; checked before deployed worker mutation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import uuid
import zipfile

from .config import read_config, exact_keys
from .paths import load_profile, NodeProfile
from .protocol import LocalHandError
from .provenance import build_metadata, implementation_commit, core_digest

INSTALL_SCHEMA="infra-local-hand-install/v1"
ENV_PATHS={"git":"LOCAL_HAND_GIT_EXECUTABLE","ssh":"LOCAL_HAND_SSH_EXECUTABLE",
           "mailbox_key":"LOCAL_HAND_MAILBOX_SSH_KEY","known_hosts":"LOCAL_HAND_KNOWN_HOSTS"}


def _bad(message):
    return LocalHandError("installation_mismatch",message,"indeterminate")


def _absolute_file(value: str) -> str:
    p=Path(value)
    if not p.is_absolute() or not p.is_file():raise _bad("installation binding must name an existing absolute file")
    # Do not resolve the executable symlink: venv Python has a distinct identity.
    return str(p.absolute())


def verify_wheel(path: Path, metadata: dict) -> str:
    limit=64*1024*1024
    def identity(info):
        return (info.st_dev,info.st_ino,info.st_mode,info.st_nlink,
                info.st_size,info.st_mtime_ns,info.st_ctime_ns)
    try:
        # Inspect and hash the same open artifact. Reopening by name after ZIP
        # validation could bind an installation to unrelated replacement bytes.
        with path.open("rb") as stream:
            before=os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size>limit:
                raise _bad("wheel exceeds installation artifact bound or is not regular")
            if identity(path.stat())!=identity(before):raise _bad("wheel changed during verification")
            with zipfile.ZipFile(stream) as archive:
                names=archive.namelist()
                if len(names)!=len(set(names)) or sum(i.file_size for i in archive.infolist())>32*1024*1024:
                    raise _bad("wheel has duplicate entries or excessive expanded size")
                payload=set(metadata["files"])|{"local_hand/_build_metadata.json"}
                distribution="infra_local_hand-"+metadata["product_version"]+".dist-info/"
                if any(name not in payload and not (
                        name.startswith(distribution) and name[len(distribution):]
                        and all(part not in ("", ".", "..") for part in name.split("/"))
                        and "\\" not in name) for name in names):
                    raise _bad("wheel contains an unbound payload entry")
                expected=(Path(__file__).parent/"_build_metadata.json").read_bytes()
                if archive.read("local_hand/_build_metadata.json")!=expected:raise _bad("wheel metadata differs from installed package")
                for name,digest in metadata["files"].items():
                    if hashlib.sha256(archive.read(name)).hexdigest()!=digest:raise _bad("wheel payload differs from installed package")
            stream.seek(0)
            digest=hashlib.sha256();count=0
            while chunk:=stream.read(min(1024*1024,limit+1-count)):
                count+=len(chunk)
                if count>limit:raise _bad("wheel exceeds installation artifact bound")
                digest.update(chunk)
            if (count!=before.st_size or identity(os.fstat(stream.fileno()))!=identity(before)
                    or identity(path.stat())!=identity(before)):
                raise _bad("wheel changed during verification")
            return digest.hexdigest()
    except (OSError,ValueError,zipfile.BadZipFile,KeyError) as exc:raise _bad("invalid wheel artifact") from exc


def create_record(profile_path: Path, output: Path, *, install_instance_id: str,
                  bindings: dict[str,str], state_root: Path, mailbox_root: Path, wheel: Path | None = None) -> dict:
    profile=load_profile(profile_path)
    metadata=build_metadata()
    if metadata is None:raise _bad("stamp the staged package or install a built wheel first")
    try:valid_uuid=str(uuid.UUID(install_instance_id))==install_instance_id
    except ValueError:valid_uuid=False
    if not valid_uuid:raise _bad("install_instance_id must be a canonical UUID")
    if metadata["artifact_kind"]=="wheel" and wheel is None:raise _bad("wheel installation requires its retained original artifact")
    wheel_path=_absolute_file(str(wheel)) if wheel is not None else None
    wheel_digest=verify_wheel(Path(wheel_path),metadata) if wheel_path else None
    if set(bindings)!=set(ENV_PATHS):raise _bad("all runtime path bindings are required")
    record={"schema_version":INSTALL_SCHEMA,"install_instance_id":install_instance_id,
            "implementation_commit":implementation_commit(),"package_digest":core_digest(),
            "profile_digest":profile.profile_sha256,"profile_path":_absolute_file(str(profile_path.absolute())),
            "python":_absolute_file(sys.executable),"bindings":{k:_absolute_file(v) for k,v in bindings.items()},
            "wheel_path":wheel_path,"wheel_sha256":wheel_digest,
            "state_root":str(state_root.resolve()),"mailbox_root":str(mailbox_root.resolve()),
            "projects_root":str(profile.projects_root),"package_root":str(Path(__file__).resolve().parent),
            "build_metadata_sha256":hashlib.sha256((Path(__file__).parent/"_build_metadata.json").read_bytes()).hexdigest()}
    data=(json.dumps(record,sort_keys=True,indent=2)+"\n").encode()
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as f:f.write(data);f.flush();os.fsync(f.fileno())
    return record


def verify_record(profile: NodeProfile, profile_path: Path, *, state_root: Path, mailbox_root: Path) -> None:
    value=os.environ.get("LOCAL_HAND_INSTALL_RECORD","")
    if not value:raise _bad("LOCAL_HAND_INSTALL_RECORD is required for deployed startup")
    path=Path(_absolute_file(value));_,record=read_config(path)
    exact_keys(record,{"schema_version","install_instance_id","implementation_commit","package_digest","profile_digest",
                       "profile_path","python","bindings","wheel_path","wheel_sha256","build_metadata_sha256",
                       "state_root","mailbox_root","projects_root","package_root"},"installation record")
    metadata=build_metadata()
    if metadata is None:raise _bad("deployed startup requires stamped build metadata")
    expected={"schema_version":INSTALL_SCHEMA,"install_instance_id":os.environ.get("LOCAL_HAND_INSTALL_INSTANCE_ID"),
              "implementation_commit":implementation_commit(),"package_digest":core_digest(),"profile_digest":profile.profile_sha256,
              "profile_path":str(profile_path.absolute()),"python":str(Path(sys.executable).absolute()),
              "bindings":{k:_absolute_file(os.environ.get(v,"")) for k,v in ENV_PATHS.items()},
              "state_root":str(state_root.resolve()),"mailbox_root":str(mailbox_root.resolve()),
              "projects_root":str(profile.projects_root),"package_root":str(Path(__file__).resolve().parent),
              "build_metadata_sha256":hashlib.sha256((Path(__file__).parent/"_build_metadata.json").read_bytes()).hexdigest()}
    if any(record.get(k)!=v for k,v in expected.items()):raise _bad("runtime/profile/code bindings changed since installation")
    wheel_path=record["wheel_path"]
    if metadata["artifact_kind"]=="wheel" and wheel_path is None:raise _bad("wheel binding missing")
    if wheel_path is not None:
        if hashlib.sha256(Path(_absolute_file(wheel_path)).read_bytes()).hexdigest()!=record["wheel_sha256"]:
            raise _bad("retained wheel digest changed")
    elif record["wheel_sha256"] is not None:raise _bad("inconsistent artifact binding")


def main(argv=None):
    p=argparse.ArgumentParser(description="Record a verified installation without overwriting an existing record")
    p.add_argument("--profile",required=True,type=Path);p.add_argument("--output",required=True,type=Path)
    p.add_argument("--install-instance-id",required=True);p.add_argument("--wheel",type=Path)
    p.add_argument("--state-root",required=True,type=Path);p.add_argument("--mailbox-root",required=True,type=Path)
    for key in ENV_PATHS:p.add_argument("--"+key.replace("_","-"),required=True)
    a=p.parse_args(argv)
    try:
        create_record(a.profile,a.output,install_instance_id=a.install_instance_id,
                      bindings={key:getattr(a,key) for key in ENV_PATHS},state_root=a.state_root,mailbox_root=a.mailbox_root,wheel=a.wheel)
        print(str(a.output));return 0
    except (LocalHandError,OSError) as exc:p.exit(2,f"installation record rejected: {exc}\n")


if __name__=="__main__":raise SystemExit(main())
