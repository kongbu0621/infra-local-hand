"""The six admitted Ledger programs. Paths are resolved by the trusted registry.

This module does not execute a caller command. Slow byte checks and filesystem
observations are called only inside runner's supervised helper.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

SOURCE_COMMIT = "6bd6acfbe5c35d581891eb87275e1173e17848fc"
SCRIPT_BLOBS = {
    "tools/acceptance/a2_nas_exercise.py": "3dc8642cb3034db0e5451b5bf6dc6f4137f27f73",
    "tests/installed_snapshot_walkthrough.py": "347e07b6c32042ddf10bebb0ddfab45c703c0c14",
}
BUILD_REQUIREMENTS = ("setuptools==84.0.0", "wheel==0.48.0", "packaging==26.3")
SUITES = {"a1_resources": 8, "a1_response_boundaries": 1,
          "a2_snapshot_resources": 7, "a2_semantic_resources": 4}
KINDS = ("host.inspect", "ledger.prepare", "ledger.test.source", "ledger.test.resources",
         "ledger.test.installed_local", "ledger.nas.roundtrip")
BUDGET_KEYS = ("wall_seconds", "terminate_grace_seconds", "cpu_seconds", "memory_bytes",
               "processes", "temporary_bytes", "nas_bytes", "log_bytes", "reservation_bytes")


class LedgerPlanError(ValueError):
    code = "UNSUPPORTED"


def _path(value):
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise LedgerPlanError("admitted absolute path required")
    if value.startswith("//") or str(Path(value)) != value or ".." in Path(value).parts:
        raise LedgerPlanError("noncanonical admitted path")
    return value


def _join(root, name):
    return str(Path(_path(root)) / name)


def clean_environment(temporary, *, source=False, resources=False):
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                   "TMPDIR": temporary, "TMP": temporary, "TEMP": temporary,
                   "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                   "PIP_CONFIG_FILE": "/dev/null", "PIP_NO_INDEX": "1",
                   "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_CACHE_DIR": "1"}
    if source:
        environment["PYTHONPATH"] = "src"
    if resources:
        environment["A2_RESOURCE_TESTS"] = "1"
    return environment


def build_plan(request, profile, prepared=None, prerequisites=()):
    """Pure, non-I/O resolver. Only the registry calls this with admitted maps."""
    kind = request["kind"]
    if kind not in KINDS:
        raise LedgerPlanError("unknown fixed job kind")
    operation = request["operation_id"]
    if not re.fullmatch(r"[a-z0-9-]{1,64}", operation):
        raise LedgerPlanError("invalid operation identity")
    roots = {"work": _join(profile["work_root"], operation),
             "temporary": _join(profile.get("temporary_root", profile["work_root"]), operation + "-tmp"),
             "evidence": _join(profile.get("evidence_root", profile["work_root"]), operation + "-evidence")}
    budget = dict(profile["budgets"])
    for key in BUDGET_KEYS:
        value = budget.get(key)
        if type(value) is not int or value < (0 if key == "nas_bytes" else 1) or value > 2**53 - 1:
            raise LedgerPlanError("finite admitted budget required: " + key)
    python = _path(profile["python"])
    source = dict(profile.get("source") or {})
    cache = dict(profile.get("build_cache") or {})
    prepared = dict(prepared or {})
    for key, value in prepared.get("bindings", {}).items():
        prepared.setdefault(key, value)
    if prepared.get("evidence_state") == "SEALED": prepared["sealed"] = True
    storage = dict(profile.get("storage") or {})
    if kind == "ledger.prepare" and source.get("commit") != SOURCE_COMMIT:
        raise LedgerPlanError("Ledger source baseline mismatch")
    source_copy = _join(roots["work"], "source")
    build_python = _join(roots["work"], "build-venv/bin/python") if kind == "ledger.prepare" else prepared.get("build_python")
    runtime_python = _join(roots["work"], "runtime-venv/bin/python") if kind == "ledger.prepare" else prepared.get("runtime_python")
    if kind.startswith("ledger.") and kind != "ledger.prepare":
        for key in ("root", "source_root", "build_python", "runtime_python", "wheel"):
            _path(prepared.get(key))
        if prepared.get("source_commit") != SOURCE_COMMIT:
            raise LedgerPlanError("prepared source baseline mismatch")
    stages = []
    base_env = clean_environment(roots["temporary"])
    def add(name, argv, cwd=source_copy, source_env=False, resource_env=False):
        stages.append({"name": name, "argv": list(argv), "cwd": cwd,
                       "env": clean_environment(roots["temporary"], source=source_env, resources=resource_env)})
    if kind == "ledger.prepare":
        _path(source.get("root")); _path(cache.get("root"))
        wheel = _join(roots["work"], "wheels/infra_artifact_ledger-0.2.0a1-py3-none-any.whl")
        build_source = _join(roots["work"], "build-source")
        add("create-build-venv", [python, "-m", "venv", "--copies", _join(roots["work"], "build-venv")], roots["work"])
        add("create-runtime-venv", [python, "-m", "venv", "--copies", _join(roots["work"], "runtime-venv")], roots["work"])
        add("install-build-cache", [build_python, "-m", "pip", "install", "--no-index", "--no-deps",
            "--find-links", cache["root"], *BUILD_REQUIREMENTS], roots["work"])
        add("build-wheel", [build_python, "-m", "pip", "wheel", "--no-index", "--no-build-isolation", "--no-deps",
            "--wheel-dir", _join(roots["work"], "wheels"), build_source], roots["work"])
        add("install-wheel", [runtime_python, "-m", "pip", "install", "--no-index", "--no-deps", wheel], roots["work"])
        add("inspect-runtime", [runtime_python, "-I", "-c", "import importlib.metadata,infra_artifact_ledger,json,sqlite3,sys; print(json.dumps({'version':importlib.metadata.version('infra-artifact-ledger'),'module':infra_artifact_ledger.__file__,'python':sys.version,'sqlite':sqlite3.sqlite_version}))"], roots["work"])
        prepared = {"root": roots["work"], "source_root": source_copy, "build_python": build_python,
                    "runtime_python": runtime_python, "wheel": wheel, "source_commit": SOURCE_COMMIT}
    elif kind == "ledger.test.source":
        add("source-unittest", [build_python, "-m", "unittest", "discover", "-s", "tests", "-v"], source_env=True)
        add("source-compile", [build_python, "-m", "compileall", "-q", "src", "tests", "tools/acceptance"], source_env=True)
    elif kind == "ledger.test.resources":
        suite = request["inputs"]["suite"]
        commands = {
            "a1_resources": [build_python, "tests/test_resources.py", "-v"],
            "a1_response_boundaries": [build_python, "tests/test_response_boundaries.py", "-v"],
            "a2_snapshot_resources": [build_python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_snapshot_resources.py", "-v"],
            "a2_semantic_resources": [build_python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_snapshot_semantic_resources.py", "-v"]}
        if suite not in commands:
            raise LedgerPlanError("unknown resource suite")
        add(suite, commands[suite], source_env=True, resource_env=suite.startswith("a2_"))
    elif kind == "ledger.test.installed_local":
        add("a1-installed", [runtime_python, "-I", _join(source_copy, "tests/installed_walkthrough.py"), "--repo", source_copy], roots["work"])
        add("a2-installed-local", [runtime_python, "-I", _join(source_copy, "tests/installed_snapshot_walkthrough.py"), "--scratch-parent", _join(roots["work"], "local-parent"), "--source-commit", SOURCE_COMMIT], roots["work"])
    elif kind == "ledger.nas.roundtrip":
        if not storage.get("stable_mount_binding"):
            raise LedgerPlanError("stable NAS mount boundary is not admitted")
        add("nas-roundtrip", [runtime_python, "-I", _join(source_copy, "tools/acceptance/a2_nas_exercise.py"),
            "--local-parent", _join(roots["work"], "local-parent"), "--storage-config", _path(storage.get("config")),
            "--source-commit", SOURCE_COMMIT, "--wheel", prepared["wheel"]], roots["work"])
    readonly = [source["root"]] if source else []
    if cache: readonly.append(cache["root"])
    if kind != "ledger.prepare" and prepared: readonly.append(prepared["root"])
    if storage: readonly.append(_path(storage["config"]))
    return {"kind": kind, "operation_id": operation, "inputs": dict(request["inputs"]), "roots": roots,
            "stages": stages, "budgets": budget, "python": python, "source": source, "build_cache": cache,
            "prepared": prepared, "storage": storage, "readonly": readonly,
            "writable": list(roots.values()) + ([storage["archive_root"]] if storage else []),
            "environment": base_env, "prerequisites": list(prerequisites),
            "bindings": {"source_commit": SOURCE_COMMIT, "script_blobs": dict(SCRIPT_BLOBS)},
            "retention": "EPHEMERAL_BY_UPSTREAM_TOOL" if kind in ("ledger.test.installed_local", "ledger.test.resources") else "JOB_FILES_RETAINED"}


def _file_identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_uid, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _regular_bytes(path, *, dir_fd=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise LedgerPlanError("input must be a single-link regular file")
        chunks = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk: break
            chunks.append(chunk)
        after = os.fstat(fd)
        entry = os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
        if _file_identity(before) != _file_identity(after) or _file_identity(after) != _file_identity(entry):
            raise LedgerPlanError("input changed while observed")
        return b"".join(chunks)
    finally:
        os.close(fd)


def bounded_regular_bytes(path, maximum):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum:
            raise LedgerPlanError("bounded regular input required")
        raw = bytearray()
        while True:
            chunk = os.read(descriptor, min(65536, maximum + 1 - len(raw)))
            if not chunk: break
            raw.extend(chunk)
            if len(raw) > maximum: raise LedgerPlanError("input exceeds byte bound")
        after = os.fstat(descriptor)
        entry = os.stat(path, follow_symlinks=False)
        if _file_identity(before) != _file_identity(after) or _file_identity(after) != _file_identity(entry):
            raise LedgerPlanError("bounded input changed during read")
        return bytes(raw)
    finally:
        os.close(descriptor)


def verify_manifest(root, manifest, *, git_blobs=False, exact=True, links=None):
    """Run only in a quota-constrained helper. Reject links and extra inputs."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or root.resolve() != root:
        raise LedgerPlanError("input root must be canonical and unlinked")
    if not isinstance(manifest, dict) or not manifest or len(manifest) > 20000:
        raise LedgerPlanError("complete admitted input inventory required")
    links = links or {}
    found_links = {}
    found = {}
    descriptors, ancestors, directories, entries = [], [], [], []
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    def names_at(descriptor):
        try:
            with os.scandir(descriptor) as scan:
                return sorted(entry.name for entry in scan)
        except OSError as error:
            raise LedgerPlanError("input inventory cannot be completely observed") from error
    def visit(descriptor, prefix):
        before = os.fstat(descriptor)
        names = names_at(descriptor)
        directories.append((descriptor, before, names))
        for name in names:
            relative = prefix + name
            observed = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            # Only top-level source Git metadata is outside the blob inventory.
            if git_blobs and relative == ".git":
                if stat.S_ISLNK(observed.st_mode): raise LedgerPlanError("linked source metadata")
                continue
            entries.append((descriptor, name, observed))
            if stat.S_ISDIR(observed.st_mode):
                child = os.open(name, flags, dir_fd=descriptor)
                descriptors.append(child)
                if _file_identity(os.fstat(child)) != _file_identity(observed):
                    raise LedgerPlanError("input directory changed while observed")
                visit(child, relative + "/")
            elif stat.S_ISLNK(observed.st_mode) and relative in links:
                target = os.readlink(name, dir_fd=descriptor)
                if (links[relative] != target or target != "lib" or name != "lib64"
                        or not stat.S_ISDIR(os.stat(target, dir_fd=descriptor, follow_symlinks=False).st_mode)):
                    raise LedgerPlanError("linked input directory")
                found_links[relative] = target
            else:
                if relative not in manifest:
                    if exact or stat.S_ISLNK(observed.st_mode):
                        raise LedgerPlanError("unadmitted input file")
                    continue
                raw = _regular_bytes(name, dir_fd=descriptor)
                digest = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() if git_blobs else hashlib.sha256(raw).hexdigest()
                if digest != manifest[relative]: raise LedgerPlanError("input byte binding mismatch")
                found[relative] = digest
    try:
        descriptor = os.open(root.anchor, flags)
        descriptors.append(descriptor)
        # Pin every ancestor; O_NOFOLLOW on the final file alone does not bind it.
        for component in root.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            descriptors.append(child)
            ancestors.append((descriptor, component, child))
            descriptor = child
        visit(descriptor, "")
        for parent, name, observed in entries:
            if _file_identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) != _file_identity(observed):
                raise LedgerPlanError("input entry changed while observed")
        for descriptor, observed, names in directories:
            if names_at(descriptor) != names or _file_identity(os.fstat(descriptor)) != _file_identity(observed):
                raise LedgerPlanError("input inventory changed while observed")
        for parent, name, child in ancestors:
            entry, opened = os.stat(name, dir_fd=parent, follow_symlinks=False), os.fstat(child)
            if (entry.st_dev, entry.st_ino, entry.st_mode) != (opened.st_dev, opened.st_ino, opened.st_mode):
                raise LedgerPlanError("input ancestor changed while observed")
    finally:
        for descriptor in reversed(descriptors): os.close(descriptor)
    if found != manifest or found_links != links: raise LedgerPlanError("missing input file or link")
    return hashlib.sha256(json.dumps(found, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def check_temp_binding(expected):
    """Called separately in every actual interpreter with a clean environment."""
    path = Path(expected)
    if path.resolve() != path or path.is_symlink() or not path.is_dir():
        raise LedgerPlanError("temporary root unavailable")
    tempfile.tempdir = None
    if Path(tempfile.gettempdir()) != path:
        raise LedgerPlanError("Python temporary directory fallback detected")
    probe_fd, probe_name = tempfile.mkstemp(dir=path)
    try:
        os.write(probe_fd, b"lh-temp-binding\n"); os.fsync(probe_fd)
    finally:
        os.close(probe_fd); os.unlink(probe_name)
    return {"temporary": str(path), "device": path.stat().st_dev, "inode": path.stat().st_ino}


def verify_inputs(plan):
    result = {"inputs_stable": False, "source_commit": SOURCE_COMMIT}
    source = plan.get("source", {})
    prepared = plan.get("prepared", {})
    if plan["kind"] == "ledger.prepare":
        if source.get("commit") != SOURCE_COMMIT or any(source.get("blobs", {}).get(k) != v for k, v in SCRIPT_BLOBS.items()):
            raise LedgerPlanError("pinned Ledger source/script mismatch")
        result["source_digest"] = verify_manifest(source["root"], source["blobs"], git_blobs=True)
        cache = plan["build_cache"]
        result["cache_digest"] = verify_manifest(cache["root"], cache["files"])
        required = {"setuptools-84.0.0", "wheel-0.48.0", "packaging-26.3"}
        if any(not any(Path(name).name.startswith(prefix + "-") and name.endswith(".whl") for name in cache["files"]) for prefix in required):
            raise LedgerPlanError("fixed offline build inputs missing")
    elif plan["kind"].startswith("ledger."):
        if prepared.get("source_commit") != SOURCE_COMMIT or not prepared.get("sealed"):
            raise LedgerPlanError("prepared binding is not sealed")
        if not prepared.get("readonly_enforced"):
            raise LedgerPlanError("prepared immutable binding missing")
        for directory, dirs, files in os.walk(prepared["root"], followlinks=False):
            if Path(directory).stat().st_mode & 0o222:
                raise LedgerPlanError("prepared directory is writable")
            if any((Path(directory) / name).lstat().st_mode & 0o222 for name in files):
                raise LedgerPlanError("prepared file is writable")
        result["prepared_digest"] = verify_manifest(prepared["root"], prepared["files"], exact=True, links=prepared.get("links", {}))
        blobs = prepared.get("source_blobs", {})
        if any(blobs.get(k) != v for k, v in SCRIPT_BLOBS.items()):
            raise LedgerPlanError("prepared trusted scripts mismatch")
        result["source_digest"] = verify_manifest(prepared["source_root"], blobs, git_blobs=True)
        if hashlib.sha256(_regular_bytes(prepared["wheel"])).hexdigest() != prepared.get("wheel_digest"):
            raise LedgerPlanError("prepared wheel mismatch")
    if plan.get("storage"):
        storage = plan["storage"]
        if hashlib.sha256(_regular_bytes(storage["config"])).hexdigest() != storage["config_digest"]:
            raise LedgerPlanError("storage configuration mismatch")
        # A declaration alone is not a cross-stage mount fence. The manager must
        # additionally install and verify the admitted private mount namespace.
    result["inputs_stable"] = True
    return result


def copy_verified_source(plan):
    if plan["kind"] == "host.inspect": return
    original = plan["source"]["root"] if plan["kind"] == "ledger.prepare" else plan["prepared"]["source_root"]
    blobs = plan["source"]["blobs"] if plan["kind"] == "ledger.prepare" else plan["prepared"]["source_blobs"]
    destination = Path(plan["roots"]["work"]) / "source"
    if destination.exists(): raise LedgerPlanError("job source copy already exists")
    destination.mkdir(mode=0o700)
    for relative in sorted(blobs):
        target = destination / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise LedgerPlanError("invalid admitted relative input")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_regular_bytes(Path(original) / relative))
        target.chmod(0o600)
    verify_manifest(destination, blobs, git_blobs=True)
    if plan["kind"] == "ledger.prepare":
        shutil.copytree(destination, Path(plan["roots"]["work"]) / "build-source", symlinks=False)
        (Path(plan["roots"]["work"]) / "wheels").mkdir()
    (Path(plan["roots"]["work"]) / "local-parent").mkdir(mode=0o700)


def resource_result(suite, stdout, stderr, exit_code):
    text = stdout + "\n" + stderr
    ran = re.findall(r"^Ran (\d+) tests? in ", text, re.MULTILINE)
    good = (exit_code == 0 and ran == [str(SUITES[suite])] and
            re.search(r"^OK\s*$", text, re.MULTILINE) is not None and
            re.search(r"\b(skipped|FAILED|ERROR|FAIL:)\b", text) is None)
    return {"outcome": "SUCCEEDED" if good else "FAILED", "tests_expected": SUITES[suite],
            "tests_observed": int(ran[0]) if len(ran) == 1 else None,
            "coverage": "LOGIC_ONLY" if suite.startswith("a2_") else "PASS"}


def discover_nas_run(parent):
    """Read only the original exclusive parent; absent/ambiguous is UNKNOWN."""
    try:
        parent = Path(parent)
        if parent.is_symlink() or parent.resolve() != parent: raise LedgerPlanError("linked run parent")
        candidates = [p for p in parent.iterdir() if re.fullmatch(r"a2-nas-[0-9a-f]{32}", p.name)]
        if len(candidates) != 1: return {"outcome": "UNKNOWN", "missing": ["unique owned NAS run"]}
        run = candidates[0]
        if run.is_symlink() or not run.is_dir(): raise LedgerPlanError("invalid NAS candidate")
        facts = {name: json.loads(_regular_bytes(run / name)) for name in ("OWNED.json", "snapshot-reference.json")}
        return {"outcome": "UNKNOWN", "run_id": run.name, "observed": facts,
                "missing": ["independent published content and ownership verification"]}
    except (OSError, ValueError, LedgerPlanError):
        return {"outcome": "UNKNOWN", "missing": ["readable unique owned NAS run"]}
