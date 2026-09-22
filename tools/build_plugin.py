"""Build the separate, unconfigured Plugin asset from a clean committed tree."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid
import zipfile

from local_hand.provenance import source_commit
from local_hand.git_safety import run_hardened_git
from local_hand.protocol import LocalHandError
from local_hand_jobs.evidence import EvidenceError, _publish_create_only


def build(output: Path) -> dict:
    commit = source_commit(require_clean=True)
    root = Path(__file__).resolve().parent.parent
    prefix = "plugins/local-hand-a2/"
    tree = run_hardened_git(root, ["ls-tree", "-rz", commit, "--", prefix],
                            allow_ssh=False, timeout=10, max_stdout=1024 * 1024,
                            max_stderr=8192, text=False)
    if tree.returncode:
        raise ValueError("Cannot inspect committed Plugin tree")
    files = {}
    for record in tree.stdout.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, kind, blob = header.split()
        rel = raw_path.decode("utf-8")
        name = rel.removeprefix(prefix)
        if (not rel.startswith(prefix) or mode not in (b"100644", b"100755") or kind != b"blob"
                or not name or ".." in Path(name).parts or "\\" in name):
            raise ValueError("Unsupported committed Plugin member")
        path = root / rel
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError("Plugin member is not regular")
        raw = path.read_bytes()
        if hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest() != blob.decode("ascii"):
            raise ValueError("Plugin bytes changed during build")
        files[name] = raw
    plugin = json.loads(files["plugin.json"])
    contract = json.loads(files["contract.json"])
    manifest = {"schema_version": "local-hand-plugin-distribution/v1", "source_commit": commit,
                "plugin_name": plugin["name"], "plugin_version": plugin["version"],
                "connection_state": "UNCONFIGURED_E4_REQUIRED",
                "contract_file_sha256": hashlib.sha256(files["contract.json"]).hexdigest(),
                "files": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
                          for name, raw in sorted(files.items())}}
    # It is a separate versioned asset, not executable code hidden in the wheel.
    mapping = json.loads(files["mcp.json"])
    if (set(mapping) - {"$schema", "mcpServers"} or mapping.get("mcpServers") != {}
            or not isinstance(contract, dict)):
        raise ValueError("Public Plugin must not contain a private endpoint mapping")
    files["DISTRIBUTION.json"] = (json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode()
    output = output.absolute()
    if output.parent.resolve() != output.parent:
        raise ValueError("Build output ancestors must not be linked")
    if root == output.parent or root in output.parents:
        raise ValueError("Build output must be outside the committed source tree")
    directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = Path(".plugin-build-" + str(uuid.uuid4()))
    descriptor = None
    try:
        parent_identity = os.fstat(directory)
        descriptor = os.open(temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        with os.fdopen(descriptor, "w+b") as stream:
            descriptor = None  # stream owns the descriptor from this point.
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for name, raw in sorted(files.items()):
                    info = zipfile.ZipInfo("local-hand-a2/" + name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    archive.writestr(info, raw)
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            expected_digest = hashlib.file_digest(stream, "sha256").hexdigest()
            created = os.fstat(stream.fileno())
            # Atomic create-only rename consumes only our staging entry. On any
            # failure preserve residue instead of unlinking a concurrent file.
            _publish_create_only(temporary, Path(output.name),
                                 source_dir_fd=directory, destination_dir_fd=directory)
            os.fsync(directory)
            # rename may change ctime. Freeze its new value before the final
            # read; a same-inode rewrite with restored mtime must still fail.
            published = os.fstat(stream.fileno())
            stream.seek(0)
            actual_digest = hashlib.file_digest(stream, "sha256").hexdigest()
            identity = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_size, item.st_mtime_ns)
            stable = lambda item: (*identity(item), item.st_ctime_ns, item.st_nlink)
            if (actual_digest != expected_digest
                    or identity(published) != identity(created)
                    or any(stable(item) != stable(published) for item in
                           (os.fstat(stream.fileno()), os.stat(output.name, dir_fd=directory, follow_symlinks=False)))):
                raise ValueError("Published Plugin output changed")
            named_parent = output.parent.lstat()
            if (output.parent.resolve() != output.parent or not stat.S_ISDIR(named_parent.st_mode)
                    or (named_parent.st_dev, named_parent.st_ino) != (parent_identity.st_dev, parent_identity.st_ino)):
                raise ValueError("Plugin output directory changed")
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)
    return {"path": str(output), "sha256": expected_digest,
            "size": created.st_size, "source_commit": commit,
            "members": len(files), "connection_state": manifest["connection_state"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.output), sort_keys=True))
        return 0
    except (OSError, ValueError, LocalHandError, EvidenceError) as error:
        parser.exit(2, f"Plugin build failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
