"""Explicit Q2 candidate verifier/installer; never imported by the wheel.

The caller owns the original deadline, bounded command capture and retained
preparation record. Every command is supplied to that caller's ``command``;
this module does not spawn an unbounded process or download a dependency.
An interrupted installation is retained and its destination is never reused.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import sys
import zipfile

SCHEMA = "local-hand-q2-installation/v1"
PACKAGES = ("local_hand", "local_hand_connect", "local_hand_jobs", "local_hand_mcp")
MAX_BYTES = 256 * 1024 * 1024
FILE_LIMIT = 16 * 1024 * 1024
MAX_FILES = 8192
METADATA = "local_hand/_build_metadata.json"


def require(test, code):
    if not test:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "BUILD_DUPLICATE_KEY")
        result[key] = value
    return result


def document(raw):
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("BUILD_NUMBER")))


def canonical(path):
    value = str(path)
    require(value.startswith("/") and not value.startswith("//") and str(Path(value)) == value
            and ".." not in Path(value).parts and value != "/", "BUILD_PATH")
    return Path(value)


def regular(path, maximum=FILE_LIMIT):
    """Read one stable, single-linked regular file, without following links."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= maximum,
                "BUILD_FILE")
        raw = bytearray()
        while len(raw) <= maximum:
            chunk = os.read(fd, min(65536, maximum + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
        require(len(raw) <= maximum and all(getattr(before, k) == getattr(after, k) for k in fields),
                "BUILD_CHANGED")
        return bytes(raw)
    finally:
        os.close(fd)


def parents(path, *, protected=False, ordinary=None):
    path = canonical(path)
    for current in (*reversed(path.parents), path):
        info = current.lstat()
        require(stat.S_ISDIR(info.st_mode), "BUILD_ANCESTOR")
        if protected:
            require(info.st_uid == 0 and not info.st_mode & 0o022, "BUILD_PROTECTION")
        if ordinary:
            uid, gid = ordinary
            shift = 6 if info.st_uid == uid else 3 if info.st_gid == gid else 0
            require((info.st_mode >> shift) & 5 == 5, "BUILD_ORDINARY_ACCESS")
    return path


def pin(path):
    path = canonical(path)
    parents(path.parent, protected=True)
    info = path.lstat()
    require(info.st_uid == 0 and not info.st_mode & 0o6022 and info.st_mode & 0o111,
            "BUILD_EXECUTABLE")
    raw = regular(path)
    require(raw[:4] == b"\x7fELF", "BUILD_ELF")
    try:
        os.getxattr(path, "security.capability", follow_symlinks=False)
    except OSError as error:
        import errno
        require(error.errno in (errno.ENODATA, errno.ENOTSUP, errno.EOPNOTSUPP), "BUILD_FILE_CAPABILITY")
    else:
        raise ValueError("BUILD_FILE_CAPABILITY")
    return {"path": str(path), "sha256": sha(raw)}


def git(source, command, *args):
    value = command(["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
                     "-c", "core.autocrlf=false", "-C", str(source), *args])
    require(type(value) is bytes and len(value) <= 4 * 1024 * 1024, "BUILD_COMMAND_OUTPUT")
    return value


def verify_source(source, source_commit, source_tree, command):
    """Check Git identity AND each blob: skip-worktree cannot conceal drift."""
    source = canonical(source); parents(source)
    require(re.fullmatch(r"[0-9a-f]{40}", source_commit or "") and
            re.fullmatch(r"[0-9a-f]{40}", source_tree or ""), "BUILD_SOURCE_ID")
    require(git(source, command, "rev-parse", "--show-toplevel").strip().decode() == str(source), "BUILD_SOURCE_ROOT")
    require(git(source, command, "rev-parse", "HEAD", "HEAD^{tree}").decode().split() ==
            [source_commit, source_tree], "BUILD_SOURCE_ID")
    require(not git(source, command, "status", "--porcelain=v1", "--untracked-files=all"), "BUILD_DIRTY")
    # Build products are allowed only by the existing provenance checker during
    # build; a host installation input must be a fresh clean checkout.
    require(not git(source, command, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"),
            "BUILD_IGNORED_INPUT")
    # The shared command collector has a 32 KiB per-command ceiling. Walk each
    # directory tree separately, never widen that ceiling for a repository dump.
    records = []; pending = [("", source_tree)]
    while pending:
        prefix, tree = pending.pop()
        for record in filter(None, git(source, command, "ls-tree", "-z", tree).split(b"\0")):
            header, encoded = record.split(b"\t", 1)
            mode, kind, blob = header.split(); name = encoded.decode("utf-8")
            require("/" not in name and name not in (".", ".."), "BUILD_TREE_ENTRY")
            if mode == b"040000" and kind == b"tree":
                pending.append((prefix + name + "/", blob.decode("ascii")))
            else:
                records.append(header + b"\t" + (prefix + name).encode("utf-8"))
            require(len(records) + len(pending) <= MAX_FILES, "BUILD_SOURCE_LIMIT")
    files = {}; total = 0
    for record in filter(None, records):
        header, encoded = record.split(b"\t", 1)
        mode, kind, blob = header.split(); name = encoded.decode("utf-8")
        relative = PurePosixPath(name)
        require(mode in (b"100644", b"100755") and kind == b"blob" and not relative.is_absolute()
                and ".." not in relative.parts and relative.as_posix() == name and name not in files,
                "BUILD_TREE_ENTRY")
        parents((source / name).parent)
        raw = regular(source / name); total += len(raw)
        require(total <= MAX_BYTES and len(files) < MAX_FILES, "BUILD_SOURCE_LIMIT")
        require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob.decode(),
                "BUILD_SOURCE_BYTES")
        files[name] = sha(raw)
    require(files and not git(source, command, "status", "--porcelain=v1", "--untracked-files=all"), "BUILD_DIRTY")
    require(git(source, command, "rev-parse", "HEAD", "HEAD^{tree}").decode().split() ==
            [source_commit, source_tree], "BUILD_SOURCE_CHANGED")
    return files


def verify_wheel(wheel, wheel_sha256, source_commit, source_files):
    raw = regular(wheel, 32 * 1024 * 1024)
    require(sha(raw) == wheel_sha256, "BUILD_WHEEL_DIGEST")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist(); names = [v.filename for v in infos]
        require(1 <= len(names) <= 1024 and len(names) == len(set(names)), "BUILD_WHEEL_ENTRIES")
        require(sum(v.file_size for v in infos) <= 32 * 1024 * 1024, "BUILD_WHEEL_SIZE")
        for info in infos:
            p = PurePosixPath(info.filename)
            require(not info.is_dir() and not p.is_absolute() and ".." not in p.parts
                    and p.as_posix() == info.filename and info.file_size <= FILE_LIMIT
                    and stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG), "BUILD_WHEEL_ENTRY")
        content = {name: archive.read(name) for name in names}
    metadata = document(content[METADATA])
    require(set(metadata) == {"schema_version", "product_version", "source_commit", "artifact_kind", "files"}
            and metadata["schema_version"] == "infra-local-hand-build/v1"
            and metadata["product_version"] == "0.2.0a1" and metadata["artifact_kind"] == "wheel"
            and metadata["source_commit"] == source_commit, "BUILD_WHEEL_METADATA")
    expected = {name[6:]: digest for name, digest in source_files.items()
                if re.fullmatch(r"tools/(?:" + "|".join(PACKAGES) + r")/[a-z_][a-z0-9_]*\.(?:py|sh|ps1)", name)}
    require(metadata["files"] == expected and all(p + "/__init__.py" in expected for p in PACKAGES),
            "BUILD_WHEEL_SOURCE")
    for name, digest in expected.items():
        require(name in content and sha(content[name]) == digest, "BUILD_WHEEL_PAYLOAD")
    dist = "infra_local_hand-0.2.0a1.dist-info/"
    extras = set(content) - set(expected) - {METADATA}
    require(extras and all(name.startswith(dist) and len(PurePosixPath(name).parts) == 2 for name in extras)
            and {dist + k for k in ("METADATA", "WHEEL", "RECORD")} <= extras, "BUILD_WHEEL_EXTRAS")
    require(b"Name: infra-local-hand\n" in content[dist + "METADATA"]
            and b"Version: 0.2.0a1\n" in content[dist + "METADATA"]
            and b"Root-Is-Purelib: true\n" in content[dist + "WHEEL"], "BUILD_DISTRIBUTION")
    rows = list(csv.reader(io.StringIO(content[dist + "RECORD"].decode())))
    require(len(rows) == len(content) and all(len(row) == 3 for row in rows)
            and len({row[0] for row in rows}) == len(rows) and {row[0] for row in rows} == set(content),
            "BUILD_RECORD_SET")
    for name, digest, size in rows:
        if name == dist + "RECORD":
            require(digest == size == "", "BUILD_RECORD_SELF")
        else:
            actual = base64.urlsafe_b64encode(hashlib.sha256(content[name]).digest()).rstrip(b"=").decode()
            require(digest == "sha256=" + actual and size == str(len(content[name])), "BUILD_RECORD_BYTES")
    payload_digest = sha(json.dumps({"schema_version": "infra-local-hand-full-payload/v1", "files": expected},
                                   sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii"))
    return {"content": content, "files": expected, "payload_digest": payload_digest}


def write_new(path, raw, mode=0o644):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw); stream.flush(); os.fsync(fd)
    finally:
        os.close(fd)


def mkdir_new(path, mode=0o755):
    path.mkdir(mode=mode); path.chmod(mode)


def bounded_inventory(root, *, limit=MAX_BYTES, protected=False):
    """Count allocated and logical bytes, including retained Git/build outputs."""
    total = 0; count = 0; pending = [Path(root)]
    while pending:
        path = pending.pop(); info = path.lstat(); count += 1
        require(count <= MAX_FILES and not stat.S_ISLNK(info.st_mode), "BUILD_INSTALL_ENTRIES")
        if protected:
            require(info.st_uid == 0 and not info.st_mode & 0o6022, "BUILD_PROTECTION")
        total += max(info.st_size, info.st_blocks * 512)
        require(total <= limit, "BUILD_INSTALL_BUDGET")
        if stat.S_ISDIR(info.st_mode):
            pending.extend(path.iterdir())
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "BUILD_INSTALL_FILE")
    return {"bytes": total, "entries": count, "limit": limit}


ABI_SOURCE = b'''#include <stdio.h>\n#include <linux/fs.h>\n#include <linux/quota.h>\n#include <linux/dqblk_xfs.h>\nint main(void) { printf("{\\"fsxattr_bytes\\":%zu,\\"dqblk_bytes\\":%zu,\\"qstatv_bytes\\":%zu}\\n", sizeof(struct fsxattr), sizeof(struct if_dqblk), sizeof(struct fs_quota_statv)); return 0; }\n'''


def compile_native(source, destination, compiler, command):
    native = destination / "quota_fd_query"; deps = destination / "native.d"
    flags = ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wconversion", "-Wformat=2",
             "-fstack-protector-strong", "-D_FORTIFY_SOURCE=2"]
    command([str(compiler), *flags, "-MD", "-MF", str(deps), "-MT", "quota_fd_query",
             str(source / "tools/admin/local_hand_quota_observer/quota_fd_query.c"), "-o", str(native)])
    native.chmod(0o755)
    abi_source = destination / "abi.c"; abi_program = destination / "abi"
    write_new(abi_source, ABI_SOURCE)
    command([str(compiler), *flags, str(abi_source), "-o", str(abi_program)])
    abi_program.chmod(0o755)
    abi = document(command([str(abi_program)]))
    require(set(abi) == {"fsxattr_bytes", "dqblk_bytes", "qstatv_bytes"}
            and abi["fsxattr_bytes"] == 28 and all(type(v) is int and 0 < v <= 1024 for v in abi.values()), "BUILD_ABI")
    dep_text = regular(deps).decode().replace("\\\n", " ")
    target, rest = dep_text.split(":", 1)
    require(target == "quota_fd_query", "BUILD_DEPENDENCIES")
    paths = sorted(set(shlex.split(rest)))
    require(1 <= len(paths) <= 256 and all(Path(p).is_absolute() for p in paths), "BUILD_DEPENDENCIES")
    inputs = {p: sha(regular(p)) for p in paths}
    return {"program": pin(native), "abi": abi, "compiler": pin(compiler), "flags": flags,
            "inputs": inputs, "abi_source_sha256": sha(ABI_SOURCE), "abi_program": pin(abi_program)}


def install_candidate(*, source, source_commit, source_tree, wheel, wheel_sha256, destination,
                      python, compiler, ordinary_uid, ordinary_gid, command):
    """Create one protected installation. Caller must reserve before this call."""
    require(os.geteuid() == 0 and type(ordinary_uid) is int and ordinary_uid > 0
            and type(ordinary_gid) is int and ordinary_gid > 0, "BUILD_INSTALL_IDENTITY")
    source = canonical(source); wheel = canonical(wheel); destination = canonical(destination)
    python = canonical(python); compiler = canonical(compiler)
    require(not os.path.lexists(destination), "BUILD_DESTINATION_EXISTS")
    parents(destination.parent, protected=True, ordinary=(ordinary_uid, ordinary_gid))
    parents(source, protected=True)
    parents(wheel.parent, protected=True)
    wheel_info = wheel.lstat()
    require(wheel_info.st_uid == 0 and not wheel_info.st_mode & 0o6022, "BUILD_PROTECTION")
    bounded_inventory(source, protected=True)
    require(not os.path.lexists(source / ".git/objects/info/alternates"), "BUILD_SOURCE_ALTERNATES")
    require(source != destination and source not in destination.parents and destination not in source.parents,
            "BUILD_INSTALL_OVERLAP")
    python_pin = pin(python); compiler_pin = pin(compiler)
    systemctl = pin(Path("/usr/bin/systemctl").resolve(strict=True))
    systemd_run = pin(Path("/usr/bin/systemd-run").resolve(strict=True))
    setpriv = pin(Path("/usr/bin/setpriv"))
    source_files = verify_source(source, source_commit, source_tree, command)
    verified = verify_wheel(wheel, wheel_sha256, source_commit, source_files)
    mkdir_new(destination)
    installed_source = destination / "source"; mkdir_new(installed_source)
    git(installed_source, command, "init", "--quiet")
    git(installed_source, command, "-c", "protocol.file.allow=always", "fetch", "--depth=1", "--no-tags",
        source.as_uri(), source_commit)
    git(installed_source, command, "checkout", "--quiet", "--detach", source_commit)
    copied = verify_source(installed_source, source_commit, source_tree, command)
    require(copied == source_files, "BUILD_COPIED_SOURCE")
    # Root's 077 umask must not make executable source inaccessible to the
    # ordinary resident. No owner or content of old objects is changed.
    for folder, dirs, names in os.walk(installed_source):
        Path(folder).chmod(0o755)
        for name in names:
            path = Path(folder) / name
            require(not path.is_symlink(), "BUILD_SOURCE_LINK")
            path.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
    runtime = destination / "runtime"
    command([str(python), "-I", "-B", "-m", "venv", "--copies", "--without-pip", str(runtime)])
    runtime_python = runtime / "bin/python3"
    require(not runtime_python.is_symlink(), "BUILD_RUNTIME_SYMLINK")
    # venv creates an optional lib64 -> lib convenience alias. It is not an
    # admitted code path; discard that newly created alias before inventory.
    lib64 = runtime / "lib64"
    if lib64.is_symlink() and os.readlink(lib64) == "lib":
        lib64.unlink()
    details = document(command([str(runtime_python), "-I", "-B", "-c",
        "import json,sys,sysconfig; print(json.dumps({'site':sysconfig.get_path('purelib'),'version':list(sys.version_info[:2])}))"]))
    require(details["version"] == [3, 12], "BUILD_PYTHON_VERSION")
    site = canonical(details["site"])
    require(runtime in site.parents, "BUILD_RUNTIME_SITE")
    for name, raw in verified["content"].items():
        path = site / name
        if not path.parent.exists():
            mkdir_new(path.parent)
        write_new(path, raw)
    # The regular copied interpreter and all installed files are immutable to
    # the ordinary user; no site .pth, dependencies, or console scripts added.
    for folder, dirs, names in os.walk(runtime):
        Path(folder).chmod(0o755)
        for name in names:
            path = Path(folder) / name
            require(not path.is_symlink(), "BUILD_RUNTIME_SYMLINK")
            path.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
    native_dir = destination / "native"; mkdir_new(native_dir)
    native_build = compile_native(installed_source, native_dir, compiler, command)
    ordinary_code = (
        "import json,os,importlib.metadata as m; from local_hand.provenance import implementation_commit,full_payload_digest; "
        "print(json.dumps({'uid':os.getuid(),'euid':os.geteuid(),'gid':os.getgid(),'groups':os.getgroups(),"
        "'commit':implementation_commit(),'payload_digest':full_payload_digest(),"
        "'packages':sorted((d.metadata['Name'],d.version) for d in m.distributions()),"
        "'status':open('/proc/self/status').read()}))")
    observed = document(command([setpriv["path"], "--reuid=" + str(ordinary_uid), "--regid=" + str(ordinary_gid),
        "--clear-groups", "--no-new-privs", "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all",
        str(runtime_python), "-I", "-B", "-c", ordinary_code]))
    require(observed["uid"] == observed["euid"] == ordinary_uid and observed["gid"] == ordinary_gid
            and observed["groups"] == [] and observed["commit"] == source_commit
            and observed["payload_digest"] == verified["payload_digest"]
            and observed["packages"] == [["infra-local-hand", "0.2.0a1"]], "BUILD_ORDINARY_RUNTIME")
    status = dict(line.split(":", 1) for line in observed["status"].splitlines() if ":" in line)
    require(all(int(status[k], 16) == 0 for k in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"))
            and status["NoNewPrivs"].strip() == "1", "BUILD_ORDINARY_CAPABILITIES")
    require(pin(python) == python_pin and pin(compiler) == compiler_pin
            and verify_source(source, source_commit, source_tree, command) == source_files
            and verify_source(installed_source, source_commit, source_tree, command) == source_files,
            "BUILD_FINAL_IDENTITY")
    runtime_pin = pin(runtime_python); info = runtime_python.stat()
    files = {name: digest for name, digest in source_files.items() if name.endswith(".py")
             and (name.startswith("tools/") or name.startswith("tests/e3_host/"))}
    admin_files = {name[6:]: digest for name, digest in files.items() if name.startswith("tools/")
                   and "/" in name[6:]}
    require(len(files) <= 512 and len(admin_files) <= 256, "BUILD_PACKAGE_LIMIT")
    result = {"schema": SCHEMA, "status": "INSTALLED",
        "source": {"root": str(installed_source), "commit": source_commit, "tree": source_tree, "files": files},
        "installed": {"package_root": str(site), "source_commit": source_commit,
            "payload_digest": verified["payload_digest"],
            "files": {k: v for k, v in verified["files"].items() if k.endswith(".py")},
            "programs": {"python": runtime_pin, "systemctl": systemctl, "systemd_run": systemd_run}},
        "admin": {"package_files": admin_files,
            "entry": {"path": str(installed_source / "tools/admin/local_hand_quota_observer/q2_entry.py"),
                      "sha256": source_files["tools/admin/local_hand_quota_observer/q2_entry.py"]},
            "programs": {"python": runtime_pin, "native": native_build["program"],
                         "systemctl": systemctl, "systemd_run": systemd_run}, "abi": native_build["abi"]},
        "ordinary_entry": {"path": str(installed_source / "tests/e3_host/q2_resident.py"),
                           "sha256": source_files["tests/e3_host/q2_resident.py"]},
        "native_build": native_build, "wheel": {"path": str(wheel), "sha256": wheel_sha256},
        "python_identity": {"device": info.st_dev, "inode": info.st_ino},
        "ordinary_verified": True, "inventory": bounded_inventory(destination, protected=True),
        "fixture_provisioned": False, "q2_accepted": False, "production_supported": False}
    write_new(destination / "installation.json", (json.dumps(result, sort_keys=True, indent=2) + "\n").encode())
    bounded_inventory(destination, protected=True)
    for path in (destination, native_dir, site):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Q2 candidate installation requires the original bounded preparation owner")
    parser.parse_args(argv)
    print(json.dumps({"schema": SCHEMA, "status": "BLOCKED", "reason": "ORIGINAL_PREPARATION_REQUIRED",
                      "fixture_provisioned": False, "q2_accepted": False}))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
