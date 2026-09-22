"""Bind runtime code to clean source and built payload, independently of cwd."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
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


def _git_blob_oid(path: Path) -> str:
    """Hash one regular worktree file exactly as Git hashes a blob."""
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise _bad("tracked source entries must be regular files")
        digest = hashlib.sha1()
        digest.update(b"blob " + str(info.st_size).encode("ascii") + b"\0")
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        after = path.lstat()
    except (OSError, ValueError) as exc:
        raise _bad("cannot read tracked source entry") from exc
    if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise _bad("tracked source changed while it was verified")
    return digest.hexdigest()


def _verify_tracked_tree(root: Path, commit: str) -> set[str]:
    """Bind every tracked worktree byte to HEAD, including hidden index flags."""
    tree = run_hardened_git(
        root,
        ["ls-tree", "-rz", "-r", commit, "--"],
        allow_ssh=False,
        timeout=10,
        max_stdout=16 * 1024 * 1024,
        max_stderr=8192,
        text=False,
    )
    if tree.returncode:
        raise _bad("cannot read committed source tree")
    seen: set[str] = set()
    for record in tree.stdout.split(b"\0"):
        if not record:
            continue
        try:
            header, raw_path = record.split(b"\t", 1)
            mode, kind, raw_blob = header.split()
            rel_text = raw_path.decode("utf-8")
        except (UnicodeError, ValueError) as exc:
            raise _bad("committed source tree is malformed") from exc
        rel = Path(rel_text)
        if (kind != b"blob" or mode not in (b"100644", b"100755")
                or rel.is_absolute() or not rel.parts or ".." in rel.parts
                or rel_text in seen or not re.fullmatch(r"[0-9a-f]{40}", raw_blob.decode("ascii", "ignore"))):
            raise _bad("committed source tree contains an unsupported entry")
        seen.add(rel_text)
        current = root
        for part in rel.parts[:-1]:
            current /= part
            try:
                if not stat.S_ISDIR(current.lstat().st_mode):
                    raise _bad("tracked source parent must be a real directory")
            except OSError as exc:
                raise _bad("tracked source parent is unavailable") from exc
        if _git_blob_oid(root / rel) != raw_blob.decode("ascii"):
            raise _bad("tracked source differs from committed Git blob: " + rel_text)
    if not seen:
        raise _bad("committed source tree is empty")
    return seen


_SETUPTOOLS_EGG_INFO = frozenset({
    "tools/infra_local_hand.egg-info/PKG-INFO",
    "tools/infra_local_hand.egg-info/SOURCES.txt",
    "tools/infra_local_hand.egg-info/dependency_links.txt",
    "tools/infra_local_hand.egg-info/entry_points.txt",
    "tools/infra_local_hand.egg-info/top_level.txt",
})


def _ignored_path_is_generated(rel: Path, tracked: set[str], *, allow_build_outputs: bool) -> bool:
    text = rel.as_posix()
    if text.startswith(".pytest_cache/"):
        return True
    if rel.parent.name == "__pycache__" and rel.suffix in (".pyc", ".pyo"):
        source = rel.parent.parent / (rel.name.split(".", 1)[0] + ".py")
        return source.as_posix() in tracked
    if text in _SETUPTOOLS_EGG_INFO:
        return True
    if allow_build_outputs and len(rel.parts) == 4 and rel.parts[:2] == ("build", "lib"):
        return rel.parts[2] in ("local_hand", "local_hand_connect") and rel.suffix in (".py", ".sh", ".ps1")
    return False


def _verify_ignored_tree(root: Path, tracked: set[str], *, allow_build_outputs: bool) -> None:
    """Reject ignored inputs except narrowly identified generated files."""
    result = run_hardened_git(
        root,
        ["ls-files", "--others", "--ignored", "--exclude-standard", "-z"],
        allow_ssh=False,
        timeout=10,
        max_stdout=16 * 1024 * 1024,
        max_stderr=8192,
        text=False,
    )
    if result.returncode:
        raise _bad("cannot enumerate ignored source entries")
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        try:
            rel_text = raw_path.decode("utf-8")
        except UnicodeError as exc:
            raise _bad("ignored source entry is not UTF-8") from exc
        rel = Path(rel_text)
        if rel.is_absolute() or not rel.parts or ".." in rel.parts:
            raise _bad("ignored source entry has an unsafe path")
        try:
            if not stat.S_ISREG((root / rel).lstat().st_mode):
                raise _bad("ignored generated entries must be regular files")
        except OSError as exc:
            raise _bad("ignored source entry is unavailable") from exc
        if not _ignored_path_is_generated(rel, tracked, allow_build_outputs=allow_build_outputs):
            raise _bad("build source contains an ignored non-generated entry: " + rel_text)


def source_commit(*, require_clean: bool = False, _allow_build_outputs: bool = False) -> str:
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
    if require_clean:
        if git(["status","--porcelain=v1","--untracked-files=all"]):
            raise _bad("build requires a clean committed source checkout")
        tracked = _verify_tracked_tree(root, commit)
        _verify_ignored_tree(root, tracked, allow_build_outputs=_allow_build_outputs)
    return commit


def _payload_mode(path: Path) -> int:
    info = path.lstat()
    if getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        raise _bad("payload entries must not be reparse points")
    return info.st_mode


def _verify_payload_cache(cache: Path, sources: set[str]) -> None:
    """Allow normal bytecode filenames without admitting another import tree."""
    for entry in cache.iterdir():
        if not stat.S_ISREG(_payload_mode(entry)) or not any(
            re.fullmatch(re.escape(stem) + r"\.[A-Za-z0-9_-]+(?:\.opt-[0-9]+)?\.pyc", entry.name)
            for stem in sources
        ):
            raise _bad("payload bytecode cache contains an unsupported entry")


def payload_hashes(root: Path) -> dict[str,str]:
    """Verify the packaged flat layout as well as its recorded source bytes.

    An extra import package or extension can shadow an unchanged .py file.
    Generated metadata and normal bytecode caches are the only non-payload
    entries admitted here. This is drift detection, not an OS trust boundary.
    """
    files={}
    for package in ("local_hand","local_hand_connect"):
        folder=root/package
        try:
            mode = _payload_mode(folder)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise _bad("cannot inspect payload package") from exc
        if not stat.S_ISDIR(mode):
            raise _bad("payload package must be a real directory")
        try:
            entries = sorted(folder.iterdir())
            sources = {entry.stem for entry in entries if entry.suffix == ".py"}
            for path in entries:
                mode = _payload_mode(path)
                if path.name == "__pycache__" and stat.S_ISDIR(mode):
                    _verify_payload_cache(path, sources)
                    continue
                if not stat.S_ISREG(mode):
                    raise _bad("payload entries must be regular files in the flat package layout")
                if package == "local_hand" and path.name == METADATA_NAME:
                    continue
                if path.suffix not in (".py",".sh",".ps1"):
                    raise _bad("payload package contains an unbound entry: " + path.name)
                files[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise _bad("cannot inspect payload entry") from exc
    if "local_hand/worker.py" not in files:raise _bad("worker payload is missing")
    return files


def write_build_metadata(root: Path, *, artifact_kind: str) -> dict[str,Any]:
    if artifact_kind not in ("wheel","source-staging"):raise _bad("unsupported artifact kind")
    commit=source_commit(require_clean=True, _allow_build_outputs=True)
    hashes=payload_hashes(root)
    source_root=Path(__file__).resolve().parent.parent
    # A clean status can hide ignored files or skip-worktree changes. Bind the
    # copied bytes to immutable Git blobs, not just the current working tree.
    tree=run_hardened_git(source_root.parent,
        ["ls-tree","-rz",commit,"--","tools/local_hand","tools/local_hand_connect"],
        allow_ssh=False,timeout=10,max_stdout=1024*1024,max_stderr=8192,text=False)
    if tree.returncode:raise _bad("cannot read committed payload tree")
    committed={}
    for record in tree.stdout.split(b"\0"):
        if not record:continue
        header,raw_path=record.split(b"\t",1)
        mode,kind,blob=header.split()
        path=Path(raw_path.decode("utf-8"))
        if len(path.parts)!=3 or path.suffix not in (".py",".sh",".ps1"):continue
        if mode not in (b"100644",b"100755") or kind!=b"blob":raise _bad("committed payload must use regular files")
        committed[Path(*path.parts[1:]).as_posix()]=blob.decode("ascii")
    if artifact_kind=="wheel" and set(hashes)!=set(committed):
        raise _bad("wheel payload file set differs from committed source")
    for rel,digest in hashes.items():
        source=source_root/rel
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
            raise _bad("staged payload differs from clean source: "+rel)
        raw=(root/rel).read_bytes()
        blob=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
        if committed.get(rel)!=blob:raise _bad("staged payload differs from committed Git blob: "+rel)
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
