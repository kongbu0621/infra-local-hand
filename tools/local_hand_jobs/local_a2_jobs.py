"""One installed, local-only Ledger A2 walkthrough using an admitted runtime.

The source commit is a deployment assertion, not a Git attestation. The fixed
program and all 17 source/wheel/installed Python payloads are checked separately.
The venv and its base interpreter remain trusted deployment inputs.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from . import ledger_jobs
from .contract import EXPECTED_SCHEMA, _matches, strict_loads

KIND = "ledger.test.local_a2"
SCRIPT_FILE = "tests/installed_snapshot_walkthrough.py"
SOURCE_BLOBS = {
    "src/infra_artifact_ledger/__init__.py": "1c6eaf6c61d4dadc9597620384072269e0f0db90",
    "src/infra_artifact_ledger/__main__.py": "d6dc00c4af8d5e63bd941ca42547b659256f2257",
    "src/infra_artifact_ledger/_checkpoints.py": "4074eef3dd8d01dcea320504492b92f3acf6d194",
    "src/infra_artifact_ledger/cli.py": "21cfb47214903cf2f0c88a243b97e2fb4fb6e04d",
    "src/infra_artifact_ledger/errors.py": "f28642ac43d4729bd7cc0b72620846c16e97b8bc",
    "src/infra_artifact_ledger/fingerprint.py": "81c72458329eeed7caeb4d7918c1871a5e232ea1",
    "src/infra_artifact_ledger/portable.py": "4077fd57d624b70c215e5e482286f88c9379c511",
    "src/infra_artifact_ledger/records.py": "7ff4cbc3e7099bf7464339e8456fb3e1ffed4cfd",
    "src/infra_artifact_ledger/recovery.py": "46d90e74150f069dbcdfc115d8fb157bba1fcca7",
    "src/infra_artifact_ledger/service.py": "fea8428cac264cb9cabea0017ff5829121dc36fa",
    "src/infra_artifact_ledger/snapshot_cli.py": "459f97568a1841de174474d270a0bd545752538c",
    "src/infra_artifact_ledger/snapshot_common.py": "a70dfeb897f2b313fdf6c0c1580424826bbea3be",
    "src/infra_artifact_ledger/snapshot_format.py": "8befa03444f255f804c1c4d55b9a455fc639e0f3",
    "src/infra_artifact_ledger/snapshot_sqlite.py": "baaad0f552bc4f3895c47879ffc910ae0aa42333",
    "src/infra_artifact_ledger/snapshot_storage.py": "fe56add3d925bd9b677151845b8c169ce67479d8",
    "src/infra_artifact_ledger/sqlite_store.py": "8c9ecd8acdd4a022280e6bac9954aebc48a1dd92",
    "src/infra_artifact_ledger/validation.py": "cb26e75a86c989bbb0d7fd6d18fa85dec1ab7b95",
    SCRIPT_FILE: "347e07b6c32042ddf10bebb0ddfab45c703c0c14",
}
MODULE_FILES = tuple(name for name in SOURCE_BLOBS if name != SCRIPT_FILE)
_FIELDS = frozenset(("source_root", "source_commit", "source_blobs", "runtime_root", "runtime_python",
    "runtime_python_realpath", "runtime_python_sha256", "venv_config_sha256", "package_root", "wheel",
    "wheel_sha256", "console_script_sha256"))
_PATHS = ("source_root", "runtime_root", "runtime_python", "runtime_python_realpath", "package_root", "wheel")
_HASHES = ("runtime_python_sha256", "venv_config_sha256", "wheel_sha256", "console_script_sha256")
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_WHEEL_BYTES = 64 * 1024 * 1024
SOURCE_EVIDENCE = "CALLER_ASSERTED_NOT_GIT_ATTESTED"
_STANDARD_DISTUTILS_PTH = (b"import os; var = 'SETUPTOOLS_USE_DISTUTILS'; "
    b"enabled = os.environ.get(var, 'local') == 'local'; "
    b"enabled and __import__('_distutils_hack').add_shim(); \n")


def _fail(message):
    raise ledger_jobs.LedgerPlanError(message)


def _inside(child, parent):
    return Path(child).is_relative_to(Path(parent))


def validate_runtime(value):
    """Pure configuration validation; no path is opened or resolved here."""
    if not isinstance(value, Mapping) or set(value) != _FIELDS:
        _fail("local A2 runtime descriptor fields differ")
    result = dict(value)
    for name in _PATHS:
        ledger_jobs._path(result[name])
    for name in _HASHES:
        if not isinstance(result[name], str) or not re.fullmatch(r"[0-9a-f]{64}", result[name]):
            _fail("local A2 runtime digest is malformed")
    if not isinstance(result["source_commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", result["source_commit"]):
        _fail("registered source commit is malformed")
    if not isinstance(result["source_blobs"], Mapping) or dict(result["source_blobs"]) != SOURCE_BLOBS:
        _fail("local A2 program differs from the fixed reviewed payload")
    result["source_blobs"] = dict(result["source_blobs"])
    source, runtime = result["source_root"], result["runtime_root"]
    if _inside(source, runtime) or _inside(runtime, source):
        _fail("source and installed runtime must be separate")
    if result["runtime_python"] != str(Path(runtime) / "bin/python"):
        _fail("runtime interpreter must be the registered venv bin/python")
    package = Path(result["package_root"])
    if (not _inside(package, runtime) or package.name != "infra_artifact_ledger"
            or package.parent.name != "site-packages"):
        _fail("installed package must be inside the registered runtime")
    return result


def descriptor_digest(runtime):
    return hashlib.sha256(json.dumps(validate_runtime(runtime), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _environment(temporary):
    # Python 3.11 venvs can retain setuptools' standard startup file. Its
    # exact admitted statement becomes inert without rebuilding that venv.
    return dict(ledger_jobs.clean_environment(temporary), SETUPTOOLS_USE_DISTUTILS="stdlib")


def _stage(runtime, roots):
    return {"name": "a2-installed-local", "argv": [runtime["runtime_python"], "-I", "-B",
        str(Path(runtime["source_root"]) / SCRIPT_FILE), "--scratch-parent",
        str(Path(roots["work"]) / "local-parent"), "--source-commit", runtime["source_commit"]],
        "cwd": roots["work"], "env": _environment(roots["temporary"])}


def build_plan(request, profile):
    if request.get("kind") != KIND or set(request.get("inputs", {})) != {"runtime_ref"}:
        _fail("local A2 accepts only an admitted runtime reference")
    reference = request["inputs"]["runtime_ref"]
    if not isinstance(reference, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", reference):
        _fail("invalid local A2 runtime reference")
    runtime = validate_runtime(profile["local_a2_runtimes"][reference])
    base_profile = {key: value for key, value in profile.items() if key not in ("source", "storage", "build_cache")}
    plan = ledger_jobs.build_plan(dict(request, kind="host.inspect"), base_profile)
    if plan["budgets"]["nas_bytes"] != 0:
        _fail("local A2 cannot reserve NAS writes")
    roots = plan["roots"]
    for writable in roots.values():
        for readonly in (runtime[name] for name in _PATHS):
            if _inside(writable, readonly) or _inside(readonly, writable):
                _fail("task roots overlap admitted inputs")
    plan.update(kind=KIND, runtime_ref=reference, local_a2_runtime=runtime,
        environment=_environment(roots["temporary"]),
        stages=[_stage(runtime, roots)], readonly=[runtime[key] for key in
            ("source_root", "runtime_root", "wheel", "runtime_python_realpath")],
        source={}, storage={}, build_cache={}, prepared={}, prerequisites=[],
        bindings={"source_commit": runtime["source_commit"], "source_commit_evidence": SOURCE_EVIDENCE,
                  "runtime_descriptor_digest": descriptor_digest(runtime), "wheel_digest": runtime["wheel_sha256"],
                  "script_blobs": {SCRIPT_FILE: SOURCE_BLOBS[SCRIPT_FILE]}},
        retention="JOB_FILES_RETAINED")
    return plan


def local_effects_only(execution, facts=None):
    """Pure plan proof; supplied facts must also prove runtime byte verification.

    This is only a scope predicate. It supplies no exit, stop, quiescence, or
    successful-business evidence; completion code must check those separately.
    """
    try:
        if not isinstance(execution, Mapping) or execution.get("kind") != KIND:
            return False
        runtime = validate_runtime(execution["local_a2_runtime"])
        roots = execution["roots"]
        if set(roots) != {"work", "temporary", "evidence"}:
            return False
        for path in roots.values():
            ledger_jobs._path(path)
            for readonly in (runtime[name] for name in _PATHS):
                if _inside(path, readonly) or _inside(readonly, path): return False
        if len(set(roots.values())) != 3 or any(_inside(a, b) for a in roots.values() for b in roots.values() if a != b):
            return False
        if (sorted(execution.get("writable", ())) != sorted(roots.values())
                or list(execution.get("readonly", ())) != [runtime[key] for key in
                    ("source_root", "runtime_root", "wheel", "runtime_python_realpath")]
                or any(execution.get(name) for name in ("storage", "build_cache", "prepared", "source", "prerequisites"))
                or execution["budgets"]["nas_bytes"] != 0
                or dict(execution.get("environment", {})) != _environment(roots["temporary"])):
            return False
        stages = execution["stages"]
        expected = _stage(runtime, roots)
        if len(stages) != 1 or dict(stages[0], argv=list(stages[0]["argv"]), env=dict(stages[0]["env"])) != expected:
            return False
        digest = descriptor_digest(runtime)
        bindings = execution.get("bindings", {})
        if not isinstance(bindings, Mapping):
            return False
        fixed_bindings = {
                "source_commit": runtime["source_commit"], "source_commit_evidence": SOURCE_EVIDENCE,
                "runtime_descriptor_digest": digest, "wheel_digest": runtime["wheel_sha256"],
                "script_blobs": {SCRIPT_FILE: SOURCE_BLOBS[SCRIPT_FILE]}}
        if any(bindings.get(name) != value for name, value in fixed_bindings.items()):
            return False
        # Registry attaches these provenance fields after constructing the fixed
        # execution. They survive persistence and phase/root remapping. Accept
        # that complete, validated group, never arbitrary additional bindings.
        provenance = {"expected", "local_hand_source_commit",
            "local_hand_installed_payload_digest", "local_hand_execution_entrypoint"}
        extra = set(bindings) - set(fixed_bindings)
        if extra:
            if extra != provenance or not isinstance(bindings["expected"], Mapping):
                return False
            expected_binding = dict(bindings["expected"])
            if (not _matches(expected_binding, EXPECTED_SCHEMA)
                    or ("expected" in execution and execution["expected"] != expected_binding)):
                return False
            for name, length in (("local_hand_source_commit", 40),
                                 ("local_hand_installed_payload_digest", 64)):
                if not isinstance(bindings[name], str) or not re.fullmatch(r"[0-9a-f]{%d}" % length, bindings[name]):
                    return False
            ledger_jobs._path(bindings["local_hand_execution_entrypoint"])
        if facts is not None and (facts.get("inputs_stable") is not True
                or facts.get("local_a2_runtime_verified") is not True
                or facts.get("runtime_descriptor_digest") != digest):
            return False
        return True
    except (ValueError, TypeError, KeyError, IndexError):
        return False


def _read(path, maximum=MAX_FILE_BYTES):
    path = Path(path)
    if path.resolve() != path:
        _fail("linked runtime input is not admitted")
    return ledger_jobs.bounded_regular_bytes(path, maximum)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _verify_startup_directory(site):
    for index, path in enumerate(Path(site).iterdir()):
        if index >= 4096:
            _fail("runtime site inventory exceeds bound")
        if path.name == "sitecustomize" or path.name.startswith("sitecustomize.") or path.name == "usercustomize" or path.name.startswith("usercustomize."):
            _fail("runtime startup extensions are not admitted")
        if path.name.endswith(".pth"):
            if path.name != "distutils-precedence.pth" or _read(path, 65536) != _STANDARD_DISTUTILS_PTH:
                _fail("runtime startup extensions are not admitted")


def verify_inputs(plan):
    if not local_effects_only(plan):
        _fail("local A2 execution differs from the fixed scratch-only plan")
    runtime = validate_runtime(plan["local_a2_runtime"])
    for name in ("source_root", "runtime_root", "package_root"):
        path = Path(runtime[name])
        if not path.is_dir() or path.resolve() != path:
            _fail("runtime input directory is linked or absent")
    interpreter = Path(runtime["runtime_python"])
    shadow_config = interpreter.parent / "pyvenv.cfg"
    if shadow_config.exists() or shadow_config.is_symlink():
        _fail("runtime has a shadow venv configuration")
    for executable in {str(interpreter), runtime["runtime_python_realpath"]}:
        path_config = Path(executable + "._pth")
        if path_config.exists() or path_config.is_symlink():
            _fail("runtime has an overriding Python search-path configuration")
    if str(interpreter.resolve(strict=True)) != runtime["runtime_python_realpath"]:
        _fail("venv interpreter target differs from registration")
    if _sha(_read(runtime["runtime_python_realpath"], 128 * 1024 * 1024)) != runtime["runtime_python_sha256"]:
        _fail("runtime interpreter bytes differ")
    config = _read(Path(runtime["runtime_root"]) / "pyvenv.cfg", 65536)
    if _sha(config) != runtime["venv_config_sha256"]:
        _fail("venv configuration bytes differ")
    values = {}
    for line in config.decode("utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip().lower()
            if key in values: _fail("duplicate venv setting")
            values[key] = value.strip().lower()
    if values.get("include-system-site-packages") != "false":
        _fail("runtime includes system site packages")
    site = Path(runtime["package_root"]).parent
    _verify_startup_directory(site)
    console = _read(interpreter.parent / "artifact-ledger", 65536)
    if _sha(console) != runtime["console_script_sha256"]:
        _fail("installed console entry bytes differ")
    source = {}
    for name, digest in SOURCE_BLOBS.items():
        raw = _read(Path(runtime["source_root"]) / name)
        if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != digest:
            _fail("fixed source payload differs: " + name)
        source[name] = raw
    wheel = _read(runtime["wheel"], MAX_WHEEL_BYTES)
    if _sha(wheel) != runtime["wheel_sha256"]:
        _fail("wheel bytes differ")
    installed = {}
    with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) > 256:
            _fail("duplicate or excessive wheel members")
        package_names = {name for name in names if name.startswith("infra_artifact_ledger/") and not name.endswith("/")}
        if package_names != {name.removeprefix("src/") for name in MODULE_FILES}:
            _fail("wheel package inventory differs")
        for name in MODULE_FILES:
            member = name.removeprefix("src/")
            info = archive.getinfo(member)
            if info.file_size > MAX_FILE_BYTES: _fail("wheel member exceeds bound")
            payload = archive.read(member)
            actual = _read(Path(runtime["package_root"]) / Path(name).name)
            if source[name] != payload or payload != actual:
                _fail("source, wheel and installed payload differ: " + name)
            installed[Path(name).name] = _sha(actual)
    actual_modules = {path.name for path in Path(runtime["package_root"]).iterdir() if path.name != "__pycache__"}
    if actual_modules != {Path(name).name for name in MODULE_FILES}:
        _fail("installed package inventory differs")
    return {"inputs_stable": True, "local_a2_payload_verified": True,
        "runtime_descriptor_digest": descriptor_digest(runtime), "source_commit": runtime["source_commit"],
        "source_commit_evidence": SOURCE_EVIDENCE, "wheel_digest": runtime["wheel_sha256"],
        "installed_payload_digest": _sha(json.dumps(installed, sort_keys=True, separators=(",", ":")).encode()),
        "installed_module_count": len(installed), "runtime_python_digest": runtime["runtime_python_sha256"],
        "console_script_digest": runtime["console_script_sha256"], "nas_publish_flow": "NOT_RUN"}


def prepare_run(plan, directory):
    """Create only the fresh task-owned parent; never rebuild or edit the venv."""
    if not local_effects_only(plan): _fail("invalid local A2 execution")
    parent = Path(plan["roots"]["work"]) / "local-parent"
    parent.mkdir(mode=0o700)  # no exist_ok: never silently repeat a partial run


def finish_run(plan, directory, stage):
    """An exit code alone cannot claim the eight-operation installed closure."""
    if not local_effects_only(plan) or stage.get("name") != "a2-installed-local" or stage.get("outcome") != "SUCCEEDED" or stage.get("exit_code") != 0:
        _fail("installed A2 stage did not succeed")
    raw = _read(Path(directory) / "a2-installed-local.stdout", 65536)
    if raw.count(b"\n") != 1 or not raw.endswith(b"\n"):
        _fail("installed A2 report is not one JSON line")
    if _read(Path(directory) / "a2-installed-local.stderr", 65536):
        _fail("installed A2 stage emitted stderr")
    report = strict_loads(raw, maximum_bytes=65536)
    runtime = plan["local_a2_runtime"]
    calls = [{"entry": mode, "operation": operation, "status": "PASS"}
             for mode in ("api", "cli") for operation in ("create", "verify", "restore", "check_restore")]
    required = {"result": "PASS", "package_version": "0.2.0a1", "module_path": str(Path(runtime["package_root"]) / "__init__.py"),
        "source_commit": runtime["source_commit"], "source_commit_evidence": SOURCE_EVIDENCE,
        "wheel_bytes_evidence": "NOT_ATTESTED_BY_THIS_SMOKE_TOOL; bind wheel digest separately",
        "calls": calls, "nas_publish_flow": "NOT_RUN", "nas_capability_acceptance": "NOT_ATTESTED", "nas_loss_exercise": "NOT_RUN"}
    extras = {"python", "sqlite", "platform", "work_dir"}
    if (not isinstance(report, dict) or set(report) != set(required) | extras
            or any(not isinstance(report.get(key), str) or not report[key] for key in extras)
            or any(report.get(key) != value for key, value in required.items())):
        _fail("installed A2 acceptance report does not prove the fixed local closure")
    work = Path(report.get("work_dir", ""))
    parent = Path(plan["roots"]["work"]) / "local-parent"
    if not work.is_absolute() or work.parent != parent or not work.name.startswith("a2-installed-") or work.resolve() != work or not work.is_dir():
        _fail("installed A2 output escaped its task parent")
    verified = verify_inputs(plan)
    return {"scope": "TASK_OWNED_LOCAL_A2", "report": report,
            "runtime_descriptor_digest": verified["runtime_descriptor_digest"],
            "wheel_digest": verified["wheel_digest"], "installed_payload_digest": verified["installed_payload_digest"],
            "source_commit_evidence": SOURCE_EVIDENCE, "nas_publish_flow": "NOT_RUN"}


# Run before enabling site processing or importing Ledger. The -S interpreter
# reports its own version/platform site candidates; the descriptor cannot pick
# a different, correctly copied package which normal isolated imports ignore.
_RUNTIME_PATH_PROBE = r'''
import importlib.machinery, os, pathlib, site, stat, sys
if not sys.flags.no_site or not sys.flags.isolated or not sys.flags.ignore_environment:
    raise ValueError('runtime probe must precede isolated site processing')
package_root = pathlib.Path(sys.argv[1])
runtime_root = pathlib.Path(sys.argv[3])
allowed_pth = bytes.fromhex(sys.argv[4])
if package_root.resolve() != package_root or runtime_root.resolve() != runtime_root:
    raise ValueError('linked registered runtime path')
def startup_bytes(path):
    if path.resolve() != path: raise ValueError('linked startup file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 65536:
            raise ValueError('unbounded startup file')
        raw = stream.read(65537)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_uid, value.st_gid, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if len(raw) != before.st_size or identity(before) != identity(os.fstat(stream.fileno())) or identity(before) != identity(path.stat(follow_symlinks=False)):
            raise ValueError('runtime startup file changed')
        return raw
site_directories = []
for candidate in site.getsitepackages([str(runtime_root)]):
    candidate = pathlib.Path(candidate).resolve()
    if not candidate.is_relative_to(runtime_root):
        raise ValueError('runtime site directory escaped the venv')
    if not candidate.exists():
        continue
    if not candidate.is_dir():
        raise ValueError('runtime site candidate is not a directory')
    if candidate in site_directories:
        continue
    for index, entry in enumerate(candidate.iterdir()):
        if index >= 4096:
            raise ValueError('runtime site inventory exceeds bound')
        if entry.name.endswith('.pth'):
            if entry.name != 'distutils-precedence.pth' or startup_bytes(entry) != allowed_pth:
                raise ValueError('runtime startup extensions are not admitted')
        if any(entry.name == name or entry.name.startswith(name + '.')
               for name in ('sitecustomize', 'usercustomize')):
            raise ValueError('runtime startup extensions are not admitted')
    site_directories.append(candidate)
if package_root.parent not in site_directories:
    raise ValueError('registered package is outside interpreter site directories')
search = list(sys.path) + [str(path) for path in site_directories]
for name in ('sitecustomize', 'usercustomize'):
    if importlib.machinery.PathFinder.find_spec(name, search) is not None:
        raise ValueError('unregistered runtime startup module')
spec = importlib.machinery.PathFinder.find_spec('infra_artifact_ledger', search)
if (spec is None or spec.origin is None or spec.submodule_search_locations is None
        or pathlib.Path(spec.origin).resolve() != package_root / '__init__.py'
        or [pathlib.Path(path).resolve() for path in spec.submodule_search_locations] != [package_root]):
    raise ValueError('actual Ledger import differs from the registered package')
'''


# The probe imports no Ledger code. Comparing compiled code prevents
# timestamp-valid and unchecked-hash cache substitution. Keep its two original
# arguments so bytecode-only regression probes can exercise it independently.
_BYTECODE_PROBE = r'''
import importlib.util, io, marshal, os, pathlib, stat, sys, types
root = pathlib.Path(sys.argv[1])
names = set(sys.argv[2].split(','))
if sys.flags.optimize != 0 or sys.pycache_prefix is not None:
    raise ValueError('runtime bytecode selection differs from the fixed invocation')
def read(path):
    if path.resolve() != path: raise ValueError('linked bytecode input')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 16777216:
            raise ValueError('unbounded bytecode input')
        raw = stream.read(16777217)
        after = os.fstat(stream.fileno())
        identity = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_nlink,
            item.st_uid, item.st_gid, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
        if len(raw) != info.st_size or identity(info) != identity(after) or identity(after) != identity(path.stat(follow_symlinks=False)):
            raise ValueError('bytecode input changed')
        return raw
def same_code(actual, expected):
    # CodeType equality alone omits stack size, qualified name and filename,
    # including those fields in nested functions. Keep its type-sensitive
    # constant comparison, then bind every stored code field recursively.
    if not isinstance(actual, types.CodeType) or actual != expected:
        return False
    fields = ('co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount', 'co_nlocals',
        'co_stacksize', 'co_flags', 'co_code', 'co_names', 'co_varnames',
        'co_filename', 'co_name', 'co_qualname', 'co_firstlineno', 'co_linetable',
        'co_exceptiontable', 'co_freevars', 'co_cellvars')
    if any(getattr(actual, field) != getattr(expected, field) for field in fields):
        return False
    return all(same_code(left, right) for left, right in zip(actual.co_consts, expected.co_consts)
               if isinstance(left, types.CodeType))
cache = root / '__pycache__'
if cache.exists() or cache.is_symlink():
    if not cache.is_dir() or cache.resolve() != cache: raise ValueError('linked bytecode cache')
    # Both fixed business invocations use -I without -O. Inspect only their
    # exact cache candidates; other interpreter/optimization caches cannot be
    # selected and remain unread and unchanged, regardless of directory size.
    for name in sorted(names):
        source = root / name
        path = pathlib.Path(importlib.util.cache_from_source(str(source), optimization=''))
        if not path.exists() and not path.is_symlink():
            continue
        raw = read(path)
        if len(raw) < 16 or raw[:4] != importlib.util.MAGIC_NUMBER or int.from_bytes(raw[4:8], 'little') not in (0, 1, 3):
            raise ValueError('invalid installed bytecode header')
        payload = io.BytesIO(raw[16:])
        actual = marshal.load(payload)
        if payload.tell() != len(raw) - 16 or not isinstance(actual, types.CodeType):
            raise ValueError('invalid installed bytecode payload')
        expected = compile(read(source), actual.co_filename, 'exec', dont_inherit=True, optimize=0)
        if not same_code(actual, expected): raise ValueError('installed bytecode differs from source')
print('LOCAL_A2_BYTECODE_VERIFIED')
'''


def runtime_probe_stage(plan):
    """Fixed bounded probe consumed only by the supervised runner."""
    if not local_effects_only(plan): _fail("invalid local A2 execution")
    return {"name": "a2-runtime-bytecode", "argv": [plan["local_a2_runtime"]["runtime_python"],
        "-I", "-S", "-B", "-c", _RUNTIME_PATH_PROBE + _BYTECODE_PROBE,
        plan["local_a2_runtime"]["package_root"], ",".join(sorted(Path(name).name for name in MODULE_FILES)),
        plan["local_a2_runtime"]["runtime_root"], _STANDARD_DISTUTILS_PTH.hex()],
        "cwd": plan["roots"]["work"], "env": _environment(plan["roots"]["temporary"])}


def finish_runtime_probe(plan, directory, stage):
    if (stage.get("name") != "a2-runtime-bytecode" or stage.get("outcome") != "SUCCEEDED"
            or stage.get("exit_code") != 0
            or _read(Path(directory) / "a2-runtime-bytecode.stdout", 1024) != b"LOCAL_A2_BYTECODE_VERIFIED\n"
            or _read(Path(directory) / "a2-runtime-bytecode.stderr", 65536)):
        _fail("installed runtime import path or bytecode differs from admission")
    return {"local_a2_runtime_verified": True, "installed_bytecode_verified": True,
            "installed_import_path_verified": True,
            "runtime_descriptor_digest": descriptor_digest(plan["local_a2_runtime"])}
