"""Private held-byte importer checks; these fixtures do not execute a field run."""
from __future__ import annotations

import builtins
import hashlib
import importlib.util
from pathlib import Path
import sys
import types

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Core field importer requires the Linux dispatcher", allow_module_level=True)

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "_core_candidate_loader_test", ROOT / "tests/e3_host/q2_core_delivery_dispatcher.py")
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


def setup_loader(raws):
    verified = {"source_files": {}, "projection": {"files": {}}, "wheel_files": {}}
    paths = {}
    for relative, raw in raws.items():
        digest = hashlib.sha256(raw).hexdigest()
        verified["source_files"][relative] = digest
        if d._projection_path(relative):
            verified["projection"]["files"][relative] = {"sha256": digest, "mode": 420}
        name = Path(relative).stem
        if relative.startswith("tools/") and relative.split("/")[1] in d.WHEEL_PACKAGES:
            verified["wheel_files"][relative[6:]] = digest
            path = "/installed/" + relative[6:]
        elif name in (*d.PREPARATION_HELPERS, "q2_prepare_build"):
            path = "/candidate/" + relative
        else:
            path = "/projection/" + relative
        paths[path] = raw
    effects = d.FieldEffects({})
    effects._candidate_root = "/candidate"
    effects._installation = {"status": "INSTALLED"}
    effects._installation_receipt = {
        "installed": {"package_root": "/installed"}, "source": {"root": "/projection"}}
    effects.verify_install_inputs = lambda: verified
    effects._effect_guard = lambda: None
    calls = []

    def read(path, **kwargs):
        calls.append(path)
        return paths[path], {"uid": 0, "gid": 0}

    effects.stable_read = read
    return effects, verified, paths, calls


def test_recursive_and_lazy_imports_ignore_ambient_modules_and_restore_globals(monkeypatch):
    effects, _, _, paths = setup_loader({
        "tools/local_hand_jobs/__init__.py": b"from .contract import Record\n",
        "tools/local_hand_jobs/contract.py": (
            b"from dataclasses import dataclass\n@dataclass\nclass Record:\n    number: int\n"),
        "tools/local_hand_jobs/budget.py": (
            b"from .contract import Record\ndef later():\n    from . import policy\n"
            b"    return Record(policy.VALUE)\n"),
        "tools/local_hand_jobs/policy.py": b"VALUE = 17\n",
    })
    poison = types.ModuleType("local_hand_jobs")
    poison.Record = object
    monkeypatch.setitem(sys.modules, "local_hand_jobs", poison)
    before = {key: value for key, value in sys.modules.items() if key.startswith("local_hand_jobs")}
    sys_path, importer, meta = list(sys.path), builtins.__import__, list(sys.meta_path)
    module = effects._candidate_modules(("local_hand_jobs.budget",))["local_hand_jobs.budget"]
    assert "/installed/local_hand_jobs/policy.py" not in paths
    record = module.later()
    assert record.number == 17
    assert module.Record is effects._candidate_modules(("local_hand_jobs.contract",))[
        "local_hand_jobs.contract"].Record
    assert before == {key: value for key, value in sys.modules.items() if key.startswith("local_hand_jobs")}
    assert sys.path == sys_path and builtins.__import__ is importer and sys.meta_path == meta
    assert all(path.startswith("/installed/") for path in paths)


@pytest.mark.parametrize("raw,error", [
    (b"raise ValueError('module failed')\n", ValueError),
    (b"import unapproved_ambient_plugin\n", d.DispatchError),
])
def test_failed_import_restores_existing_module_and_import_hooks(monkeypatch, raw, error):
    effects, _, _, _ = setup_loader({"tests/e3_host/q2_prepare_build.py": raw})
    previous = types.ModuleType("q2_prepare_build")
    monkeypatch.setitem(sys.modules, "q2_prepare_build", previous)
    importer, meta, path = builtins.__import__, list(sys.meta_path), list(sys.path)
    with pytest.raises(error):
        effects._candidate_modules(("q2_prepare_build",))
    assert sys.modules["q2_prepare_build"] is previous
    assert builtins.__import__ is importer and sys.meta_path == meta and sys.path == path
    assert not hasattr(effects, "_candidate_loader")


def test_missing_or_changed_digest_is_rejected_before_execution():
    effects, verified, paths, _ = setup_loader({"tests/e3_host/q2_prepare_build.py": b"VALUE = 1\n"})
    paths["/candidate/tests/e3_host/q2_prepare_build.py"] = b"raise AssertionError('must not run')\n"
    with pytest.raises(d.DispatchError, match="HELPER_CHANGED"):
        effects._candidate_helper("q2_prepare_build", verified)
    verified["source_files"].clear()
    with pytest.raises(d.DispatchError, match="HELPER_SOURCE_MISSING"):
        effects._candidate_helper("q2_prepare_build", verified)


@pytest.mark.parametrize("name", ["q2_prepare", "q2_namespace", "q2_watchdog", "../q2_prepare_driver",
                                  "admin.local_hand_quota_observer.watchdog"])
def test_unlisted_checkout_or_runtime_modules_cannot_be_loaded(name):
    effects, _, _, calls = setup_loader({})
    with pytest.raises(d.DispatchError, match="HELPER_(NAME|PROJECTION)"):
        effects._candidate_modules((name,))
    assert calls == []


def test_driver_dynamic_helper_uses_verified_bytes_not_its_path_loader():
    effects, _, _, calls = setup_loader({
        "tests/e3_host/q2_prepare_driver.py": (
            b"def helper(name):\n    raise AssertionError('path importer must not run')\n"
            b"def use():\n    return helper('q2_prepare_contract').VALUE\n"),
        "tests/e3_host/q2_prepare_contract.py": b"VALUE = 42\n",
        "tests/e3_host/q2_launcher.py": b"VALUE = 99\n",
    })
    driver = effects._candidate_modules(("q2_prepare_driver",))["q2_prepare_driver"]
    assert driver.use() == 42
    assert effects._candidate_modules(("q2_launcher",))["q2_launcher"].VALUE == 99
    assert "/projection/tests/e3_host/q2_launcher.py" in calls
    with pytest.raises(d.DispatchError, match="HELPER_NAME"):
        driver.helper("q2_prepare")


def test_current_pure_candidate_modules_and_dependencies_load_without_ambient_packages():
    paths = list((ROOT / "tools").rglob("*.py")) + list((ROOT / "tests/e3_host").glob("*.py"))
    effects, _, _, calls = setup_loader({path.relative_to(ROOT).as_posix(): path.read_bytes()
                                         for path in paths})
    names = (*d.PREPARATION_HELPERS, "admin.local_hand_quota_observer.q2_config",
             "admin.local_hand_quota_observer.controller_guard", "local_hand_jobs.budget",
             "q2_prepare_run", "q2_launcher", "q4_cancel_case", "q4_h11_recovery")
    modules = effects._candidate_modules(names)
    assert modules["q2_prepare_driver"].helper("q2_prepare_contract") is modules["q2_prepare_contract"]
    assert callable(modules["admin.local_hand_quota_observer.q2_config"].decode)
    assert callable(modules["local_hand_jobs.budget"].remaining_ns)
    assert all("namespace" not in path and "watchdog" not in path for path in calls)


def test_cached_module_set_cannot_change_verified_source_manifest():
    effects, verified, _, _ = setup_loader({"tests/e3_host/q2_prepare_build.py": b"VALUE = 1\n"})
    effects._candidate_modules(("q2_prepare_build",))
    verified["source_files"]["tests/e3_host/q2_prepare_build.py"] = "a" * 64
    with pytest.raises(d.DispatchError, match="HELPER_SOURCE_CHANGED"):
        effects._candidate_modules(("q2_prepare_build",))
