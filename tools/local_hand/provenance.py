"""Bind runtime code to clean source and built payload, independently of cwd."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from .config import read_config, exact_keys
from .git_safety import run_hardened_git
from .protocol import LocalHandError

METADATA_NAME = "_build_metadata.json"
BUILD_SCHEMA = "infra-local-hand-build/v1"
VERSION = "0.1.0a1"
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _bad(message: str) -> LocalHandError:
    return LocalHandError("provenance_mismatch", message, "indeterminate")


def core_digest() -> str:
    digest=hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py"),key=lambda p:p.name):
        digest.update(path.name.encode());digest.update(b"\0");digest.update(path.read_bytes());digest.update(b"\0")
    return digest.hexdigest()


def source_commit(*, require_clean: bool = False) -> str:
    root=Path(__file__).resolve().parents[2]
    if not (root/".git").exists():
        raise _bad("neither build metadata nor an exact source checkout is available")
    def git(args):
        result=run_hardened_git(root,args,allow_ssh=False,timeout=10,max_stdout=1024*1024,max_stderr=8192,text=True)
        if result.returncode:raise _bad("cannot verify source checkout identity")
        return result.stdout.strip()
    if Path(git(["rev-parse","--show-toplevel"])).resolve()!=root:
        raise _bad("source checkout must be the exact repository root")
    commit=git(["rev-parse","HEAD"])
    if not _COMMIT.fullmatch(commit):raise _bad("invalid source commit")
    if require_clean and git(["status","--porcelain=v1","--untracked-files=all"]):
        raise _bad("build requires a clean committed source checkout")
    return commit


def payload_hashes(root: Path) -> dict[str,str]:
    files={}
    for package in ("local_hand","local_hand_connect"):
        folder=root/package
        if not folder.is_dir():continue
        for path in sorted(folder.iterdir()):
            if path.suffix not in (".py",".sh",".ps1"):
                continue
            if path.is_symlink() or not path.is_file():raise _bad("payload entries must be regular files")
            files[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    if "local_hand/worker.py" not in files:raise _bad("worker payload is missing")
    return files


def write_build_metadata(root: Path, *, artifact_kind: str) -> dict[str,Any]:
    if artifact_kind not in ("wheel","source-staging"):raise _bad("unsupported artifact kind")
    commit=source_commit(require_clean=True)
    hashes=payload_hashes(root)
    source_root=Path(__file__).resolve().parent.parent
    for rel,digest in hashes.items():
        source=source_root/rel
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
            raise _bad("staged payload differs from clean source: "+rel)
    metadata={"schema_version":BUILD_SCHEMA,"product_version":VERSION,"source_commit":commit,
              "artifact_kind":artifact_kind,"files":hashes}
    path=root/"local_hand"/METADATA_NAME
    with path.open("x",encoding="utf-8",newline="\n") as f:
        f.write(json.dumps(metadata,sort_keys=True,indent=2)+"\n");f.flush();os.fsync(f.fileno())
    return metadata


def build_metadata() -> dict[str,Any] | None:
    path=Path(__file__).parent/METADATA_NAME
    if not path.exists():return None
    _,metadata=read_config(path)
    exact_keys(metadata,{"schema_version","product_version","source_commit","artifact_kind","files"},"build metadata")
    if (metadata["schema_version"]!=BUILD_SCHEMA or metadata["product_version"]!=VERSION
            or not isinstance(metadata["source_commit"],str) or not _COMMIT.fullmatch(metadata["source_commit"])
            or metadata["artifact_kind"] not in ("wheel","source-staging")):
        raise _bad("invalid build metadata")
    actual=payload_hashes(Path(__file__).resolve().parent.parent)
    if actual!=metadata["files"]:raise _bad("installed payload hashes differ from build metadata")
    return metadata


def implementation_commit() -> str:
    metadata=build_metadata()
    actual=metadata["source_commit"] if metadata is not None else source_commit()
    claimed=os.environ.get("LOCAL_HAND_IMPLEMENTATION_COMMIT")
    if claimed is not None and claimed!=actual:
        raise _bad("environment commit differs from actual source/build identity")
    return actual


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Inspect or stamp verified Local Hand build provenance")
    parser.add_argument("--stamp",type=Path,help="create metadata in a new copied source package root")
    args=parser.parse_args(argv)
    try:
        result=write_build_metadata(args.stamp,artifact_kind="source-staging") if args.stamp else {
            "implementation_commit":implementation_commit(),"package_digest":core_digest(),"build":build_metadata()}
        print(json.dumps(result,sort_keys=True));return 0
    except LocalHandError as exc:
        parser.exit(2,f"{exc.code}: {exc.message}\n")


if __name__=="__main__":raise SystemExit(main())
