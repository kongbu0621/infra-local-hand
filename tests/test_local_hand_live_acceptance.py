from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from local_hand.paths import _canonical_relative_posix
from local_hand.protocol import LocalHandError
from local_hand_connect import live_acceptance


class FakeAdapter:
    def __init__(self, *, wrong_provenance: bool = False) -> None:
        self.tasks: dict[str, dict[str, Any]] = {}
        self.results: dict[str, dict[str, Any]] = {}
        self.wrong_provenance = wrong_provenance

    def call(self, task: dict[str, Any], **_: Any) -> dict[str, Any]:
        task_id = task["task_id"]
        if task["target_node"].endswith("-acceptance-wrong-target"):
            raise LocalHandError("controller_wait_timeout", "not processed", "indeterminate")
        existing = self.tasks.get(task_id)
        if existing is not None and existing != task:
            raise LocalHandError("controller_task_id_conflict", "different digest", "indeterminate")
        self.tasks[task_id] = task
        if task_id in self.results:
            return self.results[task_id]

        action = task["action"]
        params = task["params"]
        error_code = None
        details: dict[str, Any] = {}
        if action == "node.status":
            details = {
                "node_id": task["target_node"],
                "effective_os_user": "local-hand",
                "service_account": "local-hand",
                "worker_pid": 1234,
                "install_instance_id": "11111111-1111-4111-8111-111111111111",
                "repositories": ["example-project"],
                "runtime_identity": {
                    "implementation_commit": "b" * 40,
                    "package_digest": "c" * 64,
                    "profile_digest": "d" * 64,
                },
            }
        elif action == "git.status":
            details = {"repository": params["repository"], "lines": ["## HEAD (no branch)"]}
        if action == "validation.run_profile":
            error_code = "validation_profile_not_allowlisted"
        elif params.get("repository") == "local-hand-acceptance-not-allowlisted":
            error_code = "repository_not_allowlisted"
        elif action == "fs.read_text":
            value = params["relative_path"]
            if "\\" in value:
                error_code = "path_separator_rejected"
            elif value.startswith("/") or ".." in value.split("/"):
                error_code = "path_escape"
            elif value.startswith(".git/"):
                error_code = "git_metadata_rejected"
            elif "\n" in value:
                error_code = "path_syntax_rejected"
            elif value == "e\u0301.txt":
                error_code = "path_unicode_normalization_rejected"
            elif value != value.replace("//", "/") or value.startswith("./") or "/./" in value or value.endswith("/"):
                error_code = "path_not_canonical"
            else:
                error_code = "windows_path_alias_rejected"
        result = {
            "status": "rejected" if error_code else "succeeded",
            "error_code": error_code,
            "error": error_code,
            "details": details,
            "task_id": task_id,
            "task_digest": "a" * 64,
            "implementation_commit": "b" * 40,
            "package_digest": "c" * 64,
            "profile_digest": "d" * 64,
        }
        self.results[task_id] = result
        return result

    def wait(self, task: dict[str, Any], **_: Any) -> dict[str, Any]:
        if self.wrong_provenance:
            raise LocalHandError("controller_provenance_mismatch", "wrong commit", "indeterminate")
        return self.results[task["task_id"]]


class UnexpectedAdapter:
    def call(self, task: dict[str, Any], **_: Any) -> dict[str, Any]:
        raise RuntimeError("transport exploded")


class DriftAdapter(FakeAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.new_git_status_calls = 0

    def call(self, task: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        existed = task["task_id"] in self.tasks
        result = super().call(task, **kwargs)
        if task["action"] == "git.status" and not existed:
            self.new_git_status_calls += 1
            if self.new_git_status_calls > 1:
                result["details"] = {"repository": task["params"]["repository"], "lines": [" M changed.txt"]}
        return result


class IdentityMismatchAdapter(FakeAdapter):
    def call(self, task: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        result = super().call(task, **kwargs)
        if task["action"] == "node.status":
            result["details"]["runtime_identity"]["package_digest"] = "e" * 64
        return result


class LiveAcceptanceTests(unittest.TestCase):
    def test_safe_matrix_passes_and_never_uses_write_action(self) -> None:
        adapter = FakeAdapter()
        wrong = FakeAdapter(wrong_provenance=True)
        with mock.patch.object(live_acceptance, "build_task", wraps=live_acceptance.build_task) as build:
            report = live_acceptance.run_live_acceptance(
                adapter,
                target_node="fixture-linux-node",
                repository="example-project",
                timeout_seconds=1,
                poll_seconds=0.01,
                wrong_target_timeout_seconds=0,
                wrong_provenance_adapter=wrong,
            )
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["safe_matrix_status"], "passed")
        self.assertEqual(report["acceptance_coverage"], "partial")
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(report["summary"]["not_executed"], 6)
        self.assertFalse(report["release_ready"])
        actions = [call.args[1] for call in build.call_args_list]
        self.assertNotIn("fs.write_text_cas", actions)

    def test_missing_wrong_provenance_adapter_is_explicit_skip(self) -> None:
        report = live_acceptance.run_live_acceptance(
            FakeAdapter(),
            target_node="fixture-linux-node",
            repository="example-project",
            timeout_seconds=1,
            poll_seconds=0.01,
            wrong_target_timeout_seconds=0,
        )
        outcome = next(item for item in report["cases"] if item["name"] == "wrong-provenance")
        self.assertEqual(outcome["verdict"], "SKIP")
        self.assertEqual(report["summary"]["skipped"], 1)
        self.assertEqual(report["safe_matrix_status"], "incomplete")
        self.assertEqual(report["status"], "failed")

    def test_evaluate_requires_exact_error_code(self) -> None:
        result = live_acceptance._evaluate(
            "case",
            "rejected",
            "expected_code",
            {"status": "rejected", "error_code": "wrong_code"},
        )
        self.assertEqual(result["verdict"], "FAIL")

    def test_unexpected_case_exception_is_collected_as_failure(self) -> None:
        outcome = live_acceptance._run_task(
            UnexpectedAdapter(),
            live_acceptance.AcceptanceCase("boom", "node.status", {}, "succeeded"),
            "fixture-linux-node",
            1,
            0.01,
        )
        self.assertEqual(outcome["verdict"], "FAIL")
        self.assertEqual(outcome["observed"]["error_code"], "acceptance_unexpected_exception")

    def test_repository_state_drift_fails_matrix(self) -> None:
        report = live_acceptance.run_live_acceptance(
            DriftAdapter(),
            target_node="fixture-linux-node",
            repository="example-project",
            timeout_seconds=1,
            poll_seconds=0.01,
            wrong_target_timeout_seconds=0,
            wrong_provenance_adapter=FakeAdapter(wrong_provenance=True),
        )
        outcome = next(item for item in report["cases"] if item["name"] == "repository-state-unchanged")
        self.assertEqual(outcome["verdict"], "FAIL")
        self.assertEqual(report["safe_matrix_status"], "failed")

    def test_node_status_runtime_identity_must_match_result_envelope(self) -> None:
        report = live_acceptance.run_live_acceptance(
            IdentityMismatchAdapter(),
            target_node="fixture-linux-node",
            repository="example-project",
            timeout_seconds=1,
            poll_seconds=0.01,
            wrong_target_timeout_seconds=0,
            wrong_provenance_adapter=FakeAdapter(wrong_provenance=True),
        )
        outcome = next(item for item in report["cases"] if item["name"] == "node-status-runtime-identity")
        self.assertEqual(outcome["verdict"], "FAIL")
        self.assertIn(
            "details.runtime_identity/envelope provenance mismatch",
            outcome["observed"]["runtime_identity_errors"],
        )

    def test_report_is_create_once(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "report.json"
            live_acceptance._write_report(path, {"status": "partial"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "partial")
            with self.assertRaises(LocalHandError) as ctx:
                live_acceptance._write_report(path, {"status": "failed"})
        self.assertEqual(ctx.exception.code, "acceptance_report_write_failed")
        self.assertEqual(ctx.exception.status, "indeterminate")

    def test_zero_progress_report_write_fails_and_removes_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "report.json"
            with mock.patch("os.write", return_value=0):
                with self.assertRaises(LocalHandError) as ctx:
                    live_acceptance._write_report(path, {"status": "partial"})
            self.assertFalse(path.exists())
        self.assertEqual(ctx.exception.code, "acceptance_report_write_failed")
        self.assertEqual(ctx.exception.status, "indeterminate")

    def test_live_path_case_expectations_match_shared_contract(self) -> None:
        path_cases = [
            case
            for case in live_acceptance._negative_cases("example-project")
            if case.action == "fs.read_text" and "relative_path" in case.params
        ]
        self.assertGreater(len(path_cases), 10)
        for case in path_cases:
            with self.subTest(case=case.name):
                with self.assertRaises(LocalHandError) as ctx:
                    _canonical_relative_posix(case.params["relative_path"], "relative_path")
                self.assertEqual(ctx.exception.code, case.expected_error_code)


if __name__ == "__main__":
    unittest.main()
