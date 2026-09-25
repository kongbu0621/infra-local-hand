"""Private pinned Q2 entry. No installation, grant issuance or public CLI."""
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import PurePosixPath
import re
import stat
import sys

def _bootstrap_read(filename, maximum):
    """Small independent loader: do not import unverified neighboring modules."""
    if (type(filename) is not str or not re.fullmatch(r"/[A-Za-z0-9_./-]{1,1023}", filename)
            or str(PurePosixPath(filename)) != filename or ".." in PurePosixPath(filename).parts
            or filename.startswith("//") or filename == "/"):
        raise ValueError("BOOTSTRAP_PATH")
    current = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        parts = PurePosixPath(filename).parts[1:]
        root = os.fstat(current)
        if root.st_uid != 0 or root.st_mode & 0o022:
            raise ValueError("BOOTSTRAP_PROTECTION")
        for index, part in enumerate(parts):
            directory = index < len(parts) - 1
            child = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
                            | (os.O_DIRECTORY if directory else 0), dir_fd=current)
            old, current = current, child
            os.close(old)
            metadata = os.fstat(current)
            valid_kind = stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
            if (not valid_kind or metadata.st_uid != 0 or metadata.st_mode & 0o022
                    or (not directory and (metadata.st_nlink != 1 or metadata.st_mode & 0o6000))):
                raise ValueError("BOOTSTRAP_PROTECTION")
        if metadata.st_size > maximum:
            raise ValueError("BOOTSTRAP_SIZE")
        data = bytearray()
        while len(data) <= maximum:
            piece = os.read(current, min(65536, maximum + 1 - len(data)))
            if not piece:
                break
            data.extend(piece)
        after = os.fstat(current)
        for name in ("st_dev", "st_ino", "st_uid", "st_gid", "st_mode", "st_nlink",
                     "st_size", "st_mtime_ns", "st_ctime_ns"):
            if getattr(after, name) != getattr(metadata, name):
                raise ValueError("BOOTSTRAP_CHANGED")
        if len(data) > maximum:
            raise ValueError("BOOTSTRAP_SIZE")
        return bytes(data)
    finally:
        os.close(current)



class Pinned(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, sources, roots):
        self.sources, self.roots = sources, roots

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] not in self.roots:
            return None
        if fullname not in self.sources:
            raise ImportError("UNPINNED_MODULE")
        return importlib.util.spec_from_loader(fullname, self, is_package=self.sources[fullname][2])

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        raw, filename, package = self.sources[module.__name__]
        module.__file__ = filename
        if package:
            module.__path__ = []
        exec(compile(raw, filename, "exec"), module.__dict__)


def bootstrap(path, digest):
    if not sys.flags.isolated or not sys.dont_write_bytecode:
        raise ValueError("ISOLATED_PYTHON_REQUIRED")
    raw = _bootstrap_read(path, 2 * 1024 * 1024)
    if not re.fullmatch(r"[0-9a-f]{64}", digest) or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("CONFIG_DIGEST")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_KEY")
            result[key] = value
        return result
    v = json.loads(raw, object_pairs_hook=pairs)
    if v["entry"]["path"] != os.path.abspath(__file__):
        raise ValueError("ENTRY_PATH")
    if hashlib.sha256(_bootstrap_read(__file__, 512 * 1024)).hexdigest() != v["entry"]["sha256"]:
        raise ValueError("ENTRY_DIGEST")
    files = v["package_files"]
    if type(files) is not dict or not 1 <= len(files) <= 256:
        raise ValueError("PACKAGE_COUNT")
    sources, roots = {}, set()
    for relative, checksum in files.items():
        if not re.fullmatch(r"(?:[a-z_][a-z0-9_]*/)+[a-z_][a-z0-9_]*\.py", relative):
            raise ValueError("PACKAGE_PATH")
        filename = v["tools_path"] + "/" + relative
        source = _bootstrap_read(filename, 512 * 1024)
        if hashlib.sha256(source).hexdigest() != checksum:
            raise ValueError("PACKAGE_DIGEST")
        package = relative.endswith("/__init__.py")
        module = relative[:-12] if package else relative[:-3]
        module = module.replace("/", ".")
        if module in sources:
            raise ValueError("PACKAGE_ALIAS")
        sources[module] = source, filename, package
        roots.add(module.split(".")[0])
    if any(name.split(".")[0] in roots for name in sys.modules):
        raise ValueError("PREIMPORTED_PACKAGE")
    # Namespace packages are synthetic and have NO filesystem search path.
    for name in list(sources):
        for count in range(1, len(name.split("."))):
            parent = ".".join(name.split(".")[:count])
            sources.setdefault(parent, (b"", "<pinned-namespace>", True))
            if not sources[parent][2]:
                raise ValueError("PACKAGE_PARENT")
    sys.meta_path.insert(0, Pinned(sources, roots))
    from admin.local_hand_quota_observer.q2_config import load
    return load(path, digest)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        if len(args) not in (3, 4) or args[0] not in ("listener", "admission", "query", "native"):
            raise ValueError("ARGUMENTS")
        if (args[0] == "native") != (len(args) == 4):
            raise ValueError("ARGUMENTS")
        config = bootstrap(args[1], args[2])
        if args[0] in ("listener", "admission"):
            from admin.local_hand_quota_observer import q2_listener
            getattr(q2_listener, args[0])(config)
        else:
            from admin.local_hand_quota_observer import q2_runtime
            if args[0] == "native":
                q2_runtime.native(config, args[3])
            else:
                q2_runtime.query(config)
        return 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError):
        os.write(2, b"Q2_ENTRY_REJECTED\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
