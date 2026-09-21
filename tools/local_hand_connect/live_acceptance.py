"""One-command, non-mutating Local Hand live acceptance orchestration."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from local_hand.bounded_io import read_regular_file_bounded
from local_hand.config import load_transport
from local_hand.protocol import LocalHandError

from .controller import (
    GitMailboxControllerAdapter,
    build_task,
    render_json,
    validate_expected_provenance,
)

REPORT_SCHEMA = "local-hand-live-acceptance/v1"


class ControllerPort(Protocol):
    def call(
        self,
        task: dict[str, Any],
        *,
        timeout_seconds: float = 120.0,
        poll_seconds: float = 2.0,
    ) -> dict[str, Any]: ...

    def wait(
        self,
        task: dict[str, Any],
        *,
        timeout_seconds: float = 120.0,
        poll_seconds: float = 2.0,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class AcceptanceCase:
    name: str
    action: str
    params: dict[str, Any]
    expected_status: str
    expected_error_code: str | None = None
    target_node: str | None = None


def _negative_cases(repository: str) -> tuple[AcceptanceCase, ...]:
    read = "fs.read_text"
    return (
        AcceptanceCase(
            "unknown-action-controller-admission",
            "unknown.action",
            {},
            "rejected",
            "action_not_allowlisted",
        ),
        AcceptanceCase(
            "missing-required-parameter-controller-admission",
            read,
            {"repository": repository},
            "rejected",
            "invalid_params",
        ),
        AcceptanceCase(
            "unknown-validation-profile",
            "validation.run_profile",
            {"repository": repository, "profile": "not-a-profile"},
            "rejected",
            "validation_profile_not_allowlisted",
        ),
        AcceptanceCase(
            "repository-not-allowlisted",
            "git.status",
            {"repository": "local-hand-acceptance-not-allowlisted"},
            "rejected",
            "repository_not_allowlisted",
        ),
        AcceptanceCase("path-parent-traversal", read, {"repository": repository, "relative_path": "../escape.txt"}, "rejected", "path_escape"),
        AcceptanceCase("path-absolute", read, {"repository": repository, "relative_path": "/etc/passwd"}, "rejected", "path_escape"),
        AcceptanceCase("path-git-metadata", read, {"repository": repository, "relative_path": ".git/config"}, "rejected", "git_metadata_rejected"),
        AcceptanceCase("path-backslash-git", read, {"repository": repository, "relative_path": ".git\\config"}, "rejected", "path_separator_rejected"),
        AcceptanceCase("path-backslash-parent", read, {"repository": repository, "relative_path": "..\\x"}, "rejected", "path_separator_rejected"),
        AcceptanceCase("path-windows-drive", read, {"repository": repository, "relative_path": "C:/Windows/win.ini"}, "rejected", "windows_path_alias_rejected"),
        AcceptanceCase("path-windows-ads", read, {"repository": repository, "relative_path": "README.md:secret"}, "rejected", "windows_path_alias_rejected"),
        AcceptanceCase("path-windows-device", read, {"repository": repository, "relative_path": "CON"}, "rejected", "windows_path_alias_rejected"),
        AcceptanceCase("path-windows-device-extension", read, {"repository": repository, "relative_path": "CON .txt"}, "rejected", "windows_path_alias_rejected"),
        AcceptanceCase("path-windows-device-superscript", read, {"repository": repository, "relative_path": "COM¹.txt"}, "rejected", "windows_path_alias_rejected"),
        AcceptanceCase("path-trailing-dot", read, {"repository": repository, "relative_path": "README.md."}, "rejected", "windows_path_alias_rejected"),
        AcceptanceCase("path-trailing-space", read, {"repository": repository, "relative_path": "README.md "}, "rejected", "windows_path_alias_rejected"),
        AcceptanceCase("path-leading-dot", read, {"repository": repository, "relative_path": "./README.md"}, "rejected", "path_not_canonical"),
        AcceptanceCase("path-repeated-separator", read, {"repository": repository, "relative_path": "docs//x"}, "rejected", "path_not_canonical"),
        AcceptanceCase("path-dot-component", read, {"repository": repository, "relative_path": "docs/./x"}, "rejected", "path_not_canonical"),
        AcceptanceCase("path-trailing-separator", read, {"repository": repository, "relative_path": "README.md/"}, "rejected", "path_not_canonical"),
        AcceptanceCase("path-non-nfc", read, {"repository": repository, "relative_path": "e\u0301.txt"}, "rejected", "path_unicode_normalization_rejected"),
        AcceptanceCase("path-ascii-control", read, {"repository": repository, "relative_path": "README.md\n"}, "rejected", "path_syntax_rejected"),
        AcceptanceCase("path-forbidden-character", read, {"repository": repository, "relative_path": "README?.md"}, "rejected", "windows_path_alias_rejected"),
    )


def _observed_from_exception(exc: LocalHandError) -> dict[str, Any]:
    return {
        "source": "controller",
        "status": exc.status,
        "error_code": exc.code,
        "error": exc.message,
    }


def _observed_from_unexpected(exc: Exception) -> dict[str, Any]:
    return {
        "source": "acceptance-runner",
        "status": "indeterminate",
        "error_code": "acceptance_unexpected_exception",
        "error": f"{type(exc).__name__}: {exc}",
    }


def _evaluate(
    name: str,
    expected_status: str,
    expected_error_code: str | None,
    observed: dict[str, Any],
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    passed = observed.get("status") == expected_status
    if expected_error_code is not None:
        passed = passed and observed.get("error_code") == expected_error_code
    return {
        "name": name,
        "verdict": "PASS" if passed else "FAIL",
        "task_id": task_id,
        "expected": {
            "status": expected_status,
            "error_code": expected_error_code,
        },
        "observed": observed,
    }


def _run_task(
    adapter: ControllerPort,
    case: AcceptanceCase,
    target_node: str,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, Any]:
    task: dict[str, Any] | None = None
    try:
        task = build_task(
            case.target_node or target_node,
            case.action,
            case.params,
        )
        result = adapter.call(
            task,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        )
        observed = {"source": "worker", **result}
    except LocalHandError as exc:
        observed = _observed_from_exception(exc)
    except Exception as exc:
        observed = _observed_from_unexpected(exc)
    return _evaluate(
        case.name,
        case.expected_status,
        case.expected_error_code,
        observed,
        task_id=task.get("task_id") if task else None,
    )


def run_live_acceptance(
    adapter: ControllerPort,
    *,
    target_node: str,
    repository: str,
    timeout_seconds: float = 60.0,
    poll_seconds: float = 2.0,
    wrong_target_timeout_seconds: float = 3.0,
    wrong_provenance_adapter: ControllerPort | None = None,
) -> dict[str, Any]:
    """Run the safe live matrix and return deterministic evidence.

    The matrix never writes to the managed project repository. It may publish
    Task/Result evidence to the already-admitted mailbox.
    """
    started = datetime.now(timezone.utc)
    cases: list[dict[str, Any]] = []

    baseline_task = build_task(target_node, "git.status", {"repository": repository})
    try:
        baseline = adapter.call(
            baseline_task,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        )
        baseline_observed = {"source": "worker", **baseline}
    except LocalHandError as exc:
        baseline = None
        baseline_observed = _observed_from_exception(exc)
    except Exception as exc:
        baseline = None
        baseline_observed = _observed_from_unexpected(exc)
    cases.append(_evaluate("baseline-git-status", "succeeded", None, baseline_observed, task_id=baseline_task["task_id"]))

    node_outcome = _run_task(
        adapter,
        AcceptanceCase("node-status-runtime-identity", "node.status", {}, "succeeded"),
        target_node,
        timeout_seconds,
        poll_seconds,
    )
    if node_outcome["verdict"] == "PASS":
        details = node_outcome["observed"].get("details")
        identity_errors: list[str] = []
        if not isinstance(details, dict):
            identity_errors.append("details must be an object")
        else:
            if not isinstance(details.get("effective_os_user"), str) or not details["effective_os_user"]:
                identity_errors.append("effective_os_user missing")
            if details.get("service_account") != details.get("effective_os_user"):
                identity_errors.append("service_account/effective_os_user mismatch")
            if isinstance(details.get("worker_pid"), bool) or not isinstance(details.get("worker_pid"), int) or details["worker_pid"] <= 0:
                identity_errors.append("worker_pid invalid")
            install_instance_id = details.get("install_instance_id")
            if not isinstance(install_instance_id, str) or not install_instance_id:
                identity_errors.append("install_instance_id missing")
            else:
                try:
                    if str(UUID(install_instance_id)) != install_instance_id:
                        identity_errors.append("install_instance_id is not canonical UUID")
                except ValueError:
                    identity_errors.append("install_instance_id is not UUID")
            if details.get("node_id") != target_node:
                identity_errors.append("details.node_id mismatch")
            repositories = details.get("repositories")
            if not isinstance(repositories, list) or repository not in repositories:
                identity_errors.append("repository missing from node status")
            provenance_fields = ("implementation_commit", "package_digest", "profile_digest")
            expected_runtime_identity = {
                field: node_outcome["observed"].get(field)
                for field in provenance_fields
            }
            if details.get("runtime_identity") != expected_runtime_identity:
                identity_errors.append("details.runtime_identity/envelope provenance mismatch")
        node_outcome["observed"]["runtime_identity_errors"] = identity_errors
        if identity_errors:
            node_outcome["verdict"] = "FAIL"
    cases.append(node_outcome)

    if baseline is not None:
        try:
            replay = adapter.call(
                baseline_task,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
            )
            replay_observed = {
                "source": "worker",
                **replay,
                "exact_result_match": replay == baseline,
            }
            replay_case = _evaluate("exact-replay", "succeeded", None, replay_observed, task_id=baseline_task["task_id"])
            if not replay_observed["exact_result_match"]:
                replay_case["verdict"] = "FAIL"
        except LocalHandError as exc:
            replay_case = _evaluate("exact-replay", "succeeded", None, _observed_from_exception(exc), task_id=baseline_task["task_id"])
        except Exception as exc:
            replay_case = _evaluate("exact-replay", "succeeded", None, _observed_from_unexpected(exc), task_id=baseline_task["task_id"])
        cases.append(replay_case)

        conflict_task = build_task(target_node, "git.diff", {"repository": repository}, task_id=baseline_task["task_id"])
        try:
            conflict = adapter.call(
                conflict_task,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
            )
            conflict_observed = {"source": "worker", **conflict}
        except LocalHandError as exc:
            conflict_observed = _observed_from_exception(exc)
        except Exception as exc:
            conflict_observed = _observed_from_unexpected(exc)
        cases.append(_evaluate("task-id-digest-conflict-controller-admission", "indeterminate", "controller_task_id_conflict", conflict_observed, task_id=baseline_task["task_id"]))

        if wrong_provenance_adapter is not None:
            try:
                wrong_provenance_adapter.wait(
                    baseline_task,
                    timeout_seconds=timeout_seconds,
                    poll_seconds=poll_seconds,
                )
                provenance_observed = {"source": "controller", "status": "succeeded", "error_code": None}
            except LocalHandError as exc:
                provenance_observed = _observed_from_exception(exc)
            except Exception as exc:
                provenance_observed = _observed_from_unexpected(exc)
            cases.append(_evaluate("wrong-provenance", "indeterminate", "controller_provenance_mismatch", provenance_observed, task_id=baseline_task["task_id"]))
        else:
            cases.append({
                "name": "wrong-provenance",
                "verdict": "SKIP",
                "task_id": baseline_task["task_id"],
                "reason": "wrong_provenance_adapter was not supplied",
            })
    else:
        for name in ("exact-replay", "task-id-digest-conflict-controller-admission", "wrong-provenance"):
            cases.append({
                "name": name,
                "verdict": "SKIP",
                "task_id": baseline_task["task_id"],
                "reason": "baseline failed",
            })

    wrong_target = AcceptanceCase(
        "wrong-target-ignored",
        "node.status",
        {},
        "indeterminate",
        "controller_wait_timeout",
        target_node=f"{target_node}-acceptance-wrong-target",
    )
    cases.append(_run_task(adapter, wrong_target, target_node, wrong_target_timeout_seconds, poll_seconds))

    for case in _negative_cases(repository):
        cases.append(_run_task(adapter, case, target_node, timeout_seconds, poll_seconds))

    final_case = AcceptanceCase(
        "post-negative-queue-liveness",
        "git.status",
        {"repository": repository},
        "succeeded",
    )
    final_outcome = _run_task(adapter, final_case, target_node, timeout_seconds, poll_seconds)
    cases.append(final_outcome)

    if baseline is None or final_outcome["verdict"] != "PASS":
        cases.append({
            "name": "repository-state-unchanged",
            "verdict": "SKIP",
            "task_id": final_outcome.get("task_id"),
            "reason": "baseline or final git.status unavailable",
        })
    else:
        before = baseline.get("details")
        after = final_outcome["observed"].get("details")
        unchanged = before == after
        cases.append({
            "name": "repository-state-unchanged",
            "verdict": "PASS" if unchanged else "FAIL",
            "task_id": final_outcome.get("task_id"),
            "expected": {"final_git_status_details_equal_baseline": True},
            "observed": {"final_git_status_details_equal_baseline": unchanged},
        })

    counts = {label: sum(item["verdict"] == label for item in cases) for label in ("PASS", "FAIL", "SKIP")}
    finished = datetime.now(timezone.utc)
    not_executed = [
        "CAS mutation and injected race",
        "worker-side malformed/unknown-action and digest-conflict quarantine injection",
        "symlink, oversized, non-UTF8 and directory fixtures",
        "validation timeout process-tree and noisy-output fixtures",
        "mailbox/result corruption, worker lock and bootstrap rollback fault injection",
        "physical Windows HP3080TI R5 conformance",
    ]
    if counts["FAIL"]:
        safe_matrix_status = "failed"
    elif counts["SKIP"]:
        safe_matrix_status = "incomplete"
    else:
        safe_matrix_status = "passed"
    return {
        "schema_version": REPORT_SCHEMA,
        "status": "partial" if safe_matrix_status == "passed" else "failed",
        "safe_matrix_status": safe_matrix_status,
        "acceptance_coverage": "partial",
        "release_ready": False,
        "release_ready_reason": "This safe GX10 matrix cannot replace mutating/recovery tests or physical Windows Reality.",
        "target_node": target_node,
        "repository": repository,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "summary": {
            "total": len(cases),
            "passed": counts["PASS"],
            "failed": counts["FAIL"],
            "skipped": counts["SKIP"],
            "not_executed": len(not_executed),
        },
        "cases": cases,
        "not_executed": not_executed,
    }


def _load_expected_provenance(path: Path) -> dict[str, Any]:
    try:
        raw = read_regular_file_bounded(
            path,
            16 * 1024,
            "controller_provenance_policy_invalid",
        )
        value = json.loads(raw.decode("utf-8"))
    except LocalHandError:
        raise
    except Exception as exc:
        raise LocalHandError("controller_provenance_policy_invalid", f"cannot read expected provenance: {exc}") from exc
    if not isinstance(value, dict):
        raise LocalHandError("controller_provenance_policy_invalid", "expected provenance must be an object")
    return validate_expected_provenance(value)


def _wrong_provenance(expected: dict[str, Any]) -> dict[str, Any]:
    wrong = dict(expected)
    commit = str(wrong.get("implementation_commit", ""))
    if len(commit) >= 1:
        wrong["implementation_commit"] = ("0" if commit[0] != "0" else "1") + commit[1:]
    return wrong


def _write_report(path: Path, report: dict[str, Any]) -> None:
    data = (render_json(report) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise LocalHandError(
            "acceptance_report_write_failed",
            f"cannot create acceptance report: {path}",
            "indeterminate",
        ) from exc
    write_error: OSError | None = None
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            chunk = os.write(fd, view[written:])
            if chunk <= 0:
                raise OSError("acceptance report write made no progress")
            written += chunk
        os.fsync(fd)
    except OSError as exc:
        write_error = exc
    finally:
        try:
            os.close(fd)
        except OSError as exc:
            if write_error is None:
                write_error = exc
    if write_error is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise LocalHandError(
            "acceptance_report_write_failed",
            f"cannot durably write acceptance report: {path}",
            "indeterminate",
        ) from write_error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the non-mutating Local Hand live acceptance matrix")
    parser.add_argument("--mailbox-repo", type=Path, required=True)
    parser.add_argument("--target-node", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-provenance-file", type=Path, required=True)
    parser.add_argument("--branch", help="must match the explicit transport policy")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--wrong-target-timeout-seconds", type=float, default=3.0)
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        expected = _load_expected_provenance(args.expected_provenance_file)
        adapter = GitMailboxControllerAdapter(
            args.mailbox_repo,
            branch=args.branch,
            policy=load_transport(args.policy),
            expected_provenance=expected,
        )
        wrong_adapter = GitMailboxControllerAdapter(
            args.mailbox_repo,
            branch=args.branch,
            policy=load_transport(args.policy),
            expected_provenance=_wrong_provenance(expected),
        )
        report = run_live_acceptance(
            adapter,
            target_node=args.target_node,
            repository=args.repository,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
            wrong_target_timeout_seconds=args.wrong_target_timeout_seconds,
            wrong_provenance_adapter=wrong_adapter,
        )
        report_path = args.report or Path(tempfile.gettempdir()) / (
            "local-hand-live-acceptance-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            + ".json"
        )
        _write_report(report_path, report)
        summary = report["summary"]
        print(
            f"LOCAL_HAND_SAFE_MATRIX={report['safe_matrix_status'].upper()} "
            f"PASS={summary['passed']} FAIL={summary['failed']} SKIP={summary['skipped']}"
        )
        print(f"LOCAL_HAND_ACCEPTANCE_COVERAGE={report['acceptance_coverage'].upper()} NOT_EXECUTED={summary['not_executed']}")
        print(f"REPORT={report_path}")
        print("LOCAL_HAND_V0_1=NOT_READY")
        return 0 if report["safe_matrix_status"] == "passed" else 1
    except LocalHandError as exc:
        print(render_json({"status": exc.status, "error_code": exc.code, "error": exc.message}), file=__import__("sys").stderr)
        return 3 if exc.status == "indeterminate" else 2


if __name__ == "__main__":
    raise SystemExit(main())
