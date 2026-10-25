"""Bind the selected administrator implementation, not historical approvals."""
from __future__ import annotations

import hashlib
import importlib.util
import marshal
import re
import sys
from pathlib import Path
import stat

from local_hand import provenance
from local_hand.git_safety import run_hardened_git
from local_hand.bounded_io import read_regular_file_bounded
from local_hand.bytecode import MAX_CACHE_BYTES, code_fingerprint

from .model import DeployError, digest


MAX_SOURCE_BYTES = 16 * 1024 * 1024


def _source_bytes(root, name):
    path = root / name
    for parent in path.parents:
        if not stat.S_ISDIR(parent.lstat().st_mode):
            raise DeployError('IMPLEMENTATION_MISMATCH', 'Selected source has an aliased ancestor')
        if parent == root: break
    return read_regular_file_bounded(path, MAX_SOURCE_BYTES, 'IMPLEMENTATION_MISMATCH')


def _verify_cache(root, cache, files):
    if sys.pycache_prefix is not None:
        raise DeployError('IMPLEMENTATION_MISMATCH', 'External source cache roots are not selected')
    if not stat.S_ISDIR(cache.lstat().st_mode):
        raise DeployError('IMPLEMENTATION_MISMATCH', 'Source bytecode cache must be a real directory')
    pattern = re.compile(r'([a-z_][a-z0-9_]*)\.' + re.escape(sys.implementation.cache_tag) + r'(?:\.opt-([12]))?\.pyc')
    for index, path in enumerate(cache.iterdir()):
        if index >= 1536:
            raise DeployError('IMPLEMENTATION_MISMATCH', 'Source bytecode cache exceeds its bound')
        match = pattern.fullmatch(path.name)
        if match is None:
            raise DeployError('IMPLEMENTATION_MISMATCH', 'Source bytecode cache has an unbound entry')
        source = cache.parent / (match[1] + '.py')
        name = source.relative_to(root).as_posix()
        if name not in files:
            raise DeployError('IMPLEMENTATION_MISMATCH', 'Source bytecode has no selected module')
        raw = _source_bytes(root, name)
        if hashlib.sha256(raw).hexdigest() != files[name]:
            raise DeployError('IMPLEMENTATION_MISMATCH', 'Source changed while binding its cache')
        actual = read_regular_file_bounded(path, MAX_CACHE_BYTES + 16, 'IMPLEMENTATION_MISMATCH')
        if len(actual) < 16 or actual[:4] != importlib.util.MAGIC_NUMBER:
            raise DeployError('IMPLEMENTATION_MISMATCH', 'Source bytecode has an unsupported format')
        observed = code_fingerprint(actual[16:])
        filenames = (str(source), name, source.relative_to(root / 'tools').as_posix())
        if not any(observed == code_fingerprint(marshal.dumps(compile(raw, filename, 'exec',
                    dont_inherit=True, optimize=int(match[2] or '0')))) for filename in filenames):
            raise DeployError('IMPLEMENTATION_MISMATCH', 'Source bytecode differs from the selected module')


def implementation_identity():
    root = Path(__file__).resolve().parents[3]
    if Path(provenance.__file__).resolve() != root / "tools/local_hand/provenance.py":
        raise DeployError("IMPLEMENTATION_MISMATCH", "Administrator and runtime must use one selected installation")
    if (root / provenance.SOURCE_PROJECTION_MANIFEST).exists():
        selected = provenance._source_projection_identity(root)
    else:
        # Check only selected implementation bytes. Unrelated documentation,
        # private evidence and retained installations do not block a repair.
        result = run_hardened_git(root, ["rev-parse", "HEAD", "HEAD^{tree}"],
            allow_ssh=False, timeout=10, max_stdout=8192, max_stderr=8192, text=True)
        values = result.stdout.split()
        if result.returncode or len(values) != 2:
            raise DeployError("IMPLEMENTATION_MISMATCH", "Selected source identity is unavailable")
        commit, tree = values
        if any(re.fullmatch(r'[0-9a-f]{40}', value) is None for value in (commit, tree)):
            raise DeployError('IMPLEMENTATION_MISMATCH', 'Selected source identity is invalid')
        result = run_hardened_git(root, ["ls-tree", "-rz", "-r", commit, "--", "tools", "tests/e3_host"],
            allow_ssh=False, timeout=10, max_stdout=16 * 1024 * 1024, max_stderr=8192, text=False)
        if result.returncode:
            raise DeployError("IMPLEMENTATION_MISMATCH", "Selected source inventory is unavailable")
        files = {}
        directories = set()
        if sys.pycache_prefix is not None:
            raise DeployError('IMPLEMENTATION_MISMATCH', 'External source cache roots are not selected')
        # admin is deliberately a namespace, not an unmanifested executable
        # package initializer. Check it before descending into its leaf packages.
        admin = root / 'tools/admin'
        if not stat.S_ISDIR(admin.lstat().st_mode):
            raise DeployError('IMPLEMENTATION_MISMATCH', 'Administrator namespace is aliased')
        for index, path in enumerate(admin.iterdir()):
            if index >= 2048:
                raise DeployError('IMPLEMENTATION_MISMATCH', 'Administrator namespace exceeds its bound')
            if not stat.S_ISDIR(path.lstat().st_mode):
                raise DeployError('IMPLEMENTATION_MISMATCH', 'Administrator namespace has an unbound entry')
            if path.name == '__pycache__' and any(path.iterdir()):
                raise DeployError('IMPLEMENTATION_MISMATCH', 'Administrator namespace has unbound bytecode')
        source_bytes = 0
        for row in result.stdout.split(b"\0"):
            if not row:
                continue
            metadata, raw_name = row.split(b"\t", 1)
            mode, kind, oid = metadata.split()
            name = raw_name.decode("utf-8")
            if not provenance._projection_path(name):
                continue
            if len(files) >= 512:
                raise DeployError('IMPLEMENTATION_MISMATCH', 'Selected source exceeds its module bound')
            path = root / name
            info = path.lstat()
            if mode not in (b"100644", b"100755") or kind != b"blob" or not stat.S_ISREG(info.st_mode):
                raise DeployError("IMPLEMENTATION_MISMATCH", "Selected source is not a regular module")
            raw = _source_bytes(root, name)
            source_bytes += len(raw)
            if source_bytes > 256 * 1024 * 1024:
                raise DeployError('IMPLEMENTATION_MISMATCH', 'Selected source exceeds its byte bound')
            observed = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
            if observed != oid.decode("ascii"):
                raise DeployError("IMPLEMENTATION_MISMATCH", "Selected implementation differs from its committed bytes")
            files[name] = hashlib.sha256(raw).hexdigest()
            if name.startswith("tools/"):
                directories.add(path.parent)
        for directory in directories:
            # Normal generated caches are harmless only when their executable
            # code is equivalent to the selected source, including admin code.
            for index, path in enumerate(directory.iterdir()):
                if index >= 2048:
                    raise DeployError('IMPLEMENTATION_MISMATCH', 'Selected source directory exceeds its bound')
                if path.name == "__pycache__":
                    _verify_cache(root, path, files)
                    continue
                if path.suffix in {".sh", ".ps1", ".json", ".md", ".c", ".h"}:
                    continue
                if path.relative_to(root).as_posix() not in files:
                    raise DeployError("IMPLEMENTATION_MISMATCH", "Selected implementation has an unbound module")
        if not provenance._SOURCE_PROJECTION_REQUIRED <= set(files):
            raise DeployError('IMPLEMENTATION_MISMATCH', 'Selected source omits a required runtime entry')
        selected = {"commit": commit, "tree": tree, "files": files}
    prefix = "tools/admin/local_hand_deploy/"
    modules = {name: value for name, value in selected["files"].items() if name.startswith(prefix)}
    if not {prefix + name for name in ("__init__.py", "cli.py", "coordinator.py", "identity.py")} <= set(modules):
        raise DeployError("IMPLEMENTATION_MISMATCH", "Installation does not contain the complete deployment entry")
    return {"source_commit": selected["commit"], "source_tree": selected["tree"],
            "adapter_digest": digest(modules)}
