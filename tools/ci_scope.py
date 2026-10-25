"""Select current H01/Q4/H11 coverage; historical suites remain opt-in."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


CORE_PATTERNS = (
    "test_local_hand_jobs_*.py",
    "test_local_hand_mcp_*.py",
    "test_local_hand_deploy_*.py",
    "test_local_hand_maintenance_gate.py",
    "test_local_hand_startup_*.py",
    "test_e3_q4_*.py",
)
CORE_FILES = (
    "test_ci_scope.py",
    "test_local_hand_resident.py",
    "test_local_hand_prepared_service.py",
    "test_local_hand_task_service.py",
    "test_local_hand_configuration.py",
    "test_local_hand_contract_boundaries.py",
    "test_local_hand_capture_start_chain.py",
    "test_local_hand_capture_interrupt.py",
    "test_local_hand_fd_ownership.py",
    "test_local_hand_read_completeness.py",
    "test_local_hand_process_chain.py",
    "test_local_hand_plugin.py",
    "test_e3_cpu_quota_serialization.py",
    "test_e3_quota_abi.py",
    "test_e3_quota_monitor.py",
    "test_e3_quota_journal.py",
    "test_e3_quota_runtime.py",
    "test_e3_quota_runtime_capture.py",
    "test_e3_quota_runtime_host.py",
    *(f"test_e3_quota_q2_{name}.py" for name in (
        "assembly", "capture", "chain", "chain_capacity", "closure",
        "coordinator", "diagnostics", "management", "namespace", "runtime",
        "service", "supervisor", "system_launcher",
    )),
)
BUILD_FILES = {
    "pyproject.toml", "setup.py", "requirements-build.txt",
    "requirements-mcp-linux-x86_64-py312.lock", "tools/build_plugin.py",
    "tools/verify_installed.py", "tools/ci_scope.py",
    ".github/workflows/local-hand-v0-1-validation.yml",
}


def select_tests(root: Path, suite: str, platform: str, changed_tests=()) -> list[str]:
    if suite not in {"core", "shared", "full"}:
        raise ValueError(f"unknown test suite: {suite}")
    tests = root / "tests"
    if suite == "full":
        selected = set(tests.rglob("test_*.py"))
    else:
        selected = {tests / name for name in CORE_FILES}
        for pattern in CORE_PATTERNS:
            selected.update(tests.glob(pattern))
        if suite == "shared":
            selected.update(tests.glob("test_local_hand_*.py"))
        for name in changed_tests:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("tests",):
                raise ValueError("changed test must be inside tests/")
            if path.name.startswith("test_") and path.suffix == ".py" and (root / path).is_file():
                selected.add(root / path)
    # Keep the existing Windows boundary: jobs/MCP/plugin require Unix ownership.
    if platform == "windows":
        selected = {p for p in selected if not p.name.startswith(("test_local_hand_jobs_", "test_local_hand_mcp_", "test_local_hand_deploy_", "test_local_hand_startup_"))
                    and p.name != "test_local_hand_maintenance_gate.py"
                    and p.name != "test_local_hand_plugin.py"}
    if not selected or any(not p.is_file() for p in selected):
        raise ValueError("test scope is empty or references a missing test")
    return sorted(p.relative_to(root).as_posix() for p in selected)


def plan(paths: list[str], *, full: bool = False, uncertain: bool = False) -> dict:
    shared = uncertain or any(p.startswith(("tools/local_hand/", "tools/local_hand_connect/"))
                              or p in BUILD_FILES for p in paths)
    fixture_changed = any(p.startswith("tests/") and p.endswith(".py")
                          and not Path(p).name.startswith("test_") for p in paths)
    changed_tests = sorted(p for p in paths if p.startswith("tests/")
                           and Path(p).name.startswith("test_") and p.endswith(".py"))
    shared_tests = any(Path(p).name.startswith("test_local_hand_")
                       and Path(p).name not in CORE_FILES
                       and not Path(p).name.startswith(("test_local_hand_jobs_", "test_local_hand_mcp_", "test_local_hand_deploy_", "test_local_hand_startup_"))
                       and Path(p).name != "test_local_hand_maintenance_gate.py"
                       for p in changed_tests)
    windows = full or shared or shared_tests or fixture_changed
    return {
        "matrix": {"os": ["ubuntu-latest", "windows-latest"] if windows else ["ubuntu-latest"]},
        "suite": "full" if full else "shared" if shared or fixture_changed else "core",
        "installation": full or shared,
        "historical": full,
        "changed_tests": changed_tests,
    }


def changed_paths(environment: dict[str, str]) -> list[str]:
    event = environment["EVENT_NAME"]
    if event == "workflow_dispatch":
        return []
    if event == "push":
        base, head = environment["PUSH_BEFORE"], environment["EXACT_SHA"]
        # Compare the complete push, not just its final commit.
        if not base or set(base) == {"0"}:
            raise ValueError("push base is unavailable")
    elif event == "pull_request":
        head = environment["PR_HEAD_SHA"]
        base = subprocess.check_output(
            ["git", "merge-base", environment["PR_BASE_SHA"], head], text=True).strip()
    else:
        raise ValueError(f"unsupported event: {event}")
    raw = subprocess.check_output(["git", "diff", "--name-only", "-z", "--no-renames", base, head, "--"])
    return [name.decode("utf-8") for name in raw.split(b"\0") if name]


def main() -> None:
    full = os.environ.get("FULL_SUITE", "false") == "true"
    try:
        paths = changed_paths(os.environ)
        result = plan(paths, full=full)
    except (KeyError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Scope uncertain ({type(error).__name__}); verify shared core on both platforms and installation")
        result = plan([], full=full, uncertain=True)
    print(json.dumps(result, indent=2))
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        for key, value in result.items():
            encoded = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
            stream.write(f"{key}={encoded}\n")


if __name__ == "__main__":
    main()
