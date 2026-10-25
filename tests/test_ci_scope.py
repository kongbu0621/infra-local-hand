"""Exercise CI selection without executing the selected business fixtures."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from ci_scope import changed_paths, plan, select_tests


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", [
    "tools/local_hand_jobs/task_session.py",
    "tools/local_hand_mcp/resident.py",
    "tools/admin/local_hand_system_manager/task_service.py",
    "tools/admin/local_hand_quota_observer/q2_management.py",
])
def test_core_repairs_keep_core_coverage_without_unrelated_platform_installation(path):
    scope = plan([path])
    assert scope["matrix"] == {"os": ["ubuntu-latest"]}
    assert scope["suite"] == "core"
    assert not scope["installation"] and not scope["historical"]


@pytest.mark.parametrize("paths", [
    ["tools/local_hand/bounded_io.py"],
    ["tools/local_hand_connect/controller.py", "tools/local_hand_mcp/auth.py"],
    ["pyproject.toml"],
    [".github/workflows/local-hand-v0-1-validation.yml"],
])
def test_shared_runtime_and_build_changes_expand_platforms_and_installation(paths):
    scope = plan(paths)
    assert scope["matrix"]["os"] == ["ubuntu-latest", "windows-latest"]
    assert scope["suite"] == "shared" and scope["installation"]
    assert not scope["historical"]


def test_core_selection_covers_submit_cancel_recover_auth_and_resource_dependencies():
    files = set(select_tests(ROOT, "core", "linux"))
    for name in (
        "test_local_hand_jobs_quota_resident_chain.py", "test_local_hand_jobs_business_stop.py",
        "test_local_hand_jobs_task_session.py", "test_e3_q4_h11_recovery.py",
        "test_local_hand_mcp_auth.py", "test_local_hand_mcp_server.py",
        "test_local_hand_resident.py", "test_local_hand_task_service.py",
        "test_local_hand_jobs_ledger.py", "test_local_hand_jobs_evidence.py",
        "test_local_hand_jobs_retired_a2.py",
        "test_e3_quota_q2_runtime.py", "test_e3_quota_q2_management.py",
    ):
        assert "tests/" + name in files
    assert "tests/test_e3_q2_core_serial_continuation.py" not in files
    assert "tests/test_e3_host_probe.py" not in files


def test_deployment_recovery_suites_are_linux_core_and_excluded_on_windows():
    recovery = {
        "tests/test_local_hand_maintenance_gate.py",
        "tests/test_local_hand_startup_guard.py",
        "tests/test_local_hand_mcp_readiness.py",
        "tests/test_local_hand_jobs_deployment.py",
        *(path.relative_to(ROOT).as_posix() for path in (ROOT / "tests").glob("test_local_hand_deploy_*.py")),
    }
    assert "tests/test_local_hand_deploy_identity.py" in recovery
    assert "tests/test_local_hand_deploy_checks.py" in recovery
    for suite in ("core", "shared", "full"):
        assert recovery <= set(select_tests(ROOT, suite, "linux"))
        # Explicit changed tests must not override the Unix-only boundary.
        assert recovery.isdisjoint(select_tests(ROOT, suite, "windows", sorted(recovery)))


def test_deployment_recovery_only_changes_keep_linux_core_selection():
    scope = plan([
        "tools/admin/local_hand_deploy/cli.py",
        "tools/local_hand_jobs/maintenance.py",
        "tools/local_hand_jobs/startup.py",
        "tools/local_hand_mcp/startup_guard.py",
        "tests/test_local_hand_deploy_checks.py",
        "tests/test_local_hand_maintenance_gate.py",
        "tests/test_local_hand_startup_guard.py",
    ])
    assert scope["matrix"] == {"os": ["ubuntu-latest"]}
    assert scope["suite"] == "core"
    assert not scope["installation"] and not scope["historical"]


def test_changed_test_is_retained_and_deleted_test_is_not_selected():
    scope = plan(["tests/test_local_hand_read_failure_chain.py", "tests/test_removed.py"])
    assert scope["matrix"]["os"] == ["ubuntu-latest", "windows-latest"]
    assert not scope["installation"]
    files = select_tests(ROOT, scope["suite"], "linux", scope["changed_tests"])
    assert "tests/test_local_hand_read_failure_chain.py" in files
    assert "tests/test_removed.py" not in files


def test_shared_fixture_change_expands_tests_without_repeating_installation():
    scope = plan(["tests/config_fixtures.py"])
    assert scope["suite"] == "shared"
    assert scope["matrix"]["os"] == ["ubuntu-latest", "windows-latest"]
    assert not scope["installation"]


def test_windows_boundary_and_manual_full_suite_preserve_existing_coverage():
    scope = plan([], full=True)
    assert scope["installation"] and scope["historical"]
    linux = set(select_tests(ROOT, scope["suite"], "linux"))
    windows = set(select_tests(ROOT, scope["suite"], "windows"))
    assert "tests/test_e3_q2_core_serial_continuation.py" in linux
    assert "tests/test_local_hand_hardening_b.py" in windows
    assert "tests/test_local_hand_jobs_task_session.py" not in windows
    assert "tests/test_local_hand_jobs_retired_a2.py" not in windows
    assert windows < linux


def test_missing_push_baseline_expands_checks_instead_of_skipping(tmp_path, monkeypatch):
    monkeypatch.setenv("EVENT_NAME", "push")
    monkeypatch.setenv("PUSH_BEFORE", "0" * 40)
    monkeypatch.setenv("EXACT_SHA", "a" * 40)
    monkeypatch.setenv("FULL_SUITE", "false")
    output = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    subprocess.run([sys.executable, str(ROOT / "tools/ci_scope.py")], check=True)
    values = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert json.loads(values["matrix"])["os"] == ["ubuntu-latest", "windows-latest"]
    assert values["suite"] == "shared" and values["installation"] == "true"


def test_complete_push_and_pr_range_include_earlier_runtime_change_and_renames(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def git(*args):
        return subprocess.check_output(["git", *args], text=True).strip()
    git("init", "-q")
    git("config", "user.name", "CI scope fixture")
    git("config", "user.email", "fixture@example.invalid")
    (tmp_path / "base").write_text("base")
    git("add", "."); git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    source = tmp_path / "tools/local_hand/运行时.py"
    source.parent.mkdir(parents=True); source.write_text("fixture")
    git("add", "."); git("commit", "-qm", "runtime")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/note.md").write_text("fixture")
    git("add", "."); git("commit", "-qm", "documentation")
    middle = git("rev-parse", "HEAD")
    for event in (
        dict(EVENT_NAME="push", PUSH_BEFORE=base, EXACT_SHA=middle),
        dict(EVENT_NAME="pull_request", PR_BASE_SHA=base, PR_HEAD_SHA=middle),
    ):
        assert plan(changed_paths(event))["installation"]
    git("mv", str(source.relative_to(tmp_path)), "docs/retained.txt")
    git("commit", "-qm", "move to docs")
    head = git("rev-parse", "HEAD")
    # Deletion/rename must retain the old runtime path in the affected scope.
    assert "docs/retained.txt" in changed_paths(dict(EVENT_NAME="push", PUSH_BEFORE=base, EXACT_SHA=head))
    for event in (
        dict(EVENT_NAME="push", PUSH_BEFORE=middle, EXACT_SHA=head),
        dict(EVENT_NAME="pull_request", PR_BASE_SHA=middle, PR_HEAD_SHA=head),
    ):
        paths = changed_paths(event)
        assert "tools/local_hand/运行时.py" in paths
        assert plan(paths)["installation"]


def test_scope_rejects_paths_outside_test_root():
    with pytest.raises(ValueError, match="inside tests"):
        select_tests(ROOT, "core", "linux", ["tests/../../other/test_escape.py"])
