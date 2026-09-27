"""Load hash-pinned Q2 orchestration helpers before guest staging exists.

Only exact, caller-supplied ``q2_*.py`` paths in one tools directory are virtual.
The D orchestration bytes are verified in full, then compiled unchanged with
their declared ``__file__``. No source text is rewritten and no installed wheel
or frozen runtime import is intercepted. The temporary hook exists only for
the caller's read-only bootstrap; leaving the context restores normal imports.
The later installed runtime must run by a fresh exec outside this context.

This is a loader for explicitly trusted orchestration, not a Python sandbox.
It has no machine-path defaults, downloads, staging writes, or execution entry.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import PurePosixPath
import re

MAX_FILES = 64
MAX_BYTES = 8 * 1024 * 1024
_NAME = re.compile(r"q2_[a-z0-9_]+\.py\Z")
_MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")


def require(value, code):
    if not value:
        raise ValueError(code)


def canonical(value):
    require(type(value) is str and 0 < len(value) <= 4096 and value.startswith("/")
            and not value.startswith("//") and "\\" not in value and "\0" not in value,
            "RETRY_BUNDLE_PATH")
    path = PurePosixPath(value)
    require(str(path) == value and ".." not in path.parts and _NAME.fullmatch(path.name),
            "RETRY_BUNDLE_PATH")
    return path


class _Loader:
    def __init__(self, owner, name, path):
        self.owner, self.name, self.path = owner, name, path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        owner = self.owner
        owner._live()
        require(module.__name__ == self.name and module.__file__ == self.path,
                "RETRY_BUNDLE_MODULE")
        require(self.path not in owner._executing, "RETRY_BUNDLE_RECURSIVE_IMPORT")
        owner._executing.add(self.path)
        try:
            # Compile bytes directly: encoding declarations and tracebacks retain
            # the exact verified source rather than a reconstructed string.
            code = compile(owner._files[self.path], self.path, "exec", dont_inherit=True)
            exec(code, module.__dict__)
        finally:
            owner._executing.remove(self.path)

    def get_filename(self, fullname):
        require(fullname == self.name, "RETRY_BUNDLE_MODULE")
        return self.path


class _VirtualTools:
    def __init__(self, files, hashes):
        require(type(files) is dict and type(hashes) is dict
                and 0 < len(files) <= MAX_FILES and set(files) == set(hashes),
                "RETRY_BUNDLE_FILES")
        verified = {}
        parent = None
        total = 0
        for path, source in files.items():
            current = canonical(path)
            if parent is None:
                parent = current.parent
            require(current.parent == parent, "RETRY_BUNDLE_DIRECTORY")
            require(type(source) in (bytes, str), "RETRY_BUNDLE_SOURCE")
            require(0 < len(source) <= MAX_BYTES - total, "RETRY_BUNDLE_SIZE")
            raw = source.encode("utf-8") if type(source) is str else source
            total += len(raw)
            require(raw and total <= MAX_BYTES, "RETRY_BUNDLE_SIZE")
            expected = hashes[path]
            require(type(expected) is str and re.fullmatch(r"[0-9a-f]{64}", expected)
                    and hashlib.sha256(raw).hexdigest() == expected, "RETRY_BUNDLE_DIGEST")
            verified[path] = raw
        self._files = verified
        self._parent = parent
        self._executing = set()
        self._original = None
        self._hook = None
        self._entered = False

    def _live(self):
        require(self._entered and importlib.util.spec_from_file_location is self._hook,
                "RETRY_BUNDLE_INACTIVE")

    def __enter__(self):
        require(not self._entered and self._original is None, "RETRY_BUNDLE_REENTRY")
        original = importlib.util.spec_from_file_location
        require(not getattr(original, "_q2_virtual_tools", False), "RETRY_BUNDLE_OVERLAP")

        def spec_from_file_location(name, location=None, *, loader=None, submodule_search_locations=None):
            self._live()
            location_text = os.fspath(location) if location is not None else None
            if type(location_text) is str and location_text in self._files:
                require(type(name) is str and _MODULE.fullmatch(name)
                        and loader is None and submodule_search_locations is None,
                        "RETRY_BUNDLE_SPEC")
                spec = importlib.machinery.ModuleSpec(name, _Loader(self, name, location_text),
                                                     origin=location_text, is_package=False)
                spec.has_location = True
                return spec
            # A missing bundled sibling must not silently load an unpinned file
            # that happens to exist on disk at the future staging location.
            if type(location_text) in (str, bytes):
                path = PurePosixPath(os.path.normpath(os.fsdecode(location_text)))
                require(not (path.parent == self._parent and _NAME.fullmatch(path.name)),
                        "RETRY_BUNDLE_UNPINNED_SIBLING")
            return original(name, location, loader=loader,
                            submodule_search_locations=submodule_search_locations)

        spec_from_file_location._q2_virtual_tools = True
        self._original = original
        self._hook = spec_from_file_location
        self._entered = True
        importlib.util.spec_from_file_location = self._hook
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            importlib.util.spec_from_file_location = self._original
        finally:
            self._entered = False
            self._executing.clear()
        return False

    def load(self, path, module_name):
        """Load one exact member, without adding it to the import module cache."""
        self._live()
        path = os.fspath(path)
        canonical(path)
        require(path in self._files, "RETRY_BUNDLE_UNPINNED_MODULE")
        require(type(module_name) is str and _MODULE.fullmatch(module_name), "RETRY_BUNDLE_MODULE")
        spec = self._hook(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def virtual_tools(files, hashes):
    """Validate all source bytes first, then temporarily load exact Q2 helpers."""
    return _VirtualTools(files, hashes)


if __name__ == "__main__":
    print(json.dumps({"status": "BLOCKED", "reason": "EXPLICIT_VERIFIED_BUNDLE_REQUIRED"}, sort_keys=True))
    raise SystemExit(2)
