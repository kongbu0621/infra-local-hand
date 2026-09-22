"""Command-line entry point for Local Hand Connect."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from local_hand.bounded_io import read_regular_file_bounded
from local_hand.config import load_transport, strict_json
from local_hand.protocol import MAX_TASK_JSON_BYTES, LocalHandError

from .controller import (
    GitMailboxControllerAdapter,
    _write_create_only,
    build_task,
    load_task_file,
    render_json,
)


def _params(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(read_regular_file_bounded(path, MAX_TASK_JSON_BYTES, "controller_params_invalid").decode("utf-8"))
    except LocalHandError:
        raise
    except Exception as exc:
        raise LocalHandError("controller_params_invalid", "params file is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise LocalHandError("controller_params_invalid", "params file must contain a JSON object")
    return value


def _expected_provenance(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        raw = read_regular_file_bounded(path, 16 * 1024, "controller_provenance_policy_invalid")
        value = strict_json(raw)
    except LocalHandError as exc:
        if exc.code == "controller_provenance_policy_invalid":
            raise
        raise LocalHandError(
            "controller_provenance_policy_invalid",
            "expected provenance file must be strict UTF-8 JSON",
        ) from exc
    if not isinstance(value, dict):
        raise LocalHandError("controller_provenance_policy_invalid", "expected provenance file must contain an object")
    return value


def _write_output(path: str, value: Any) -> None:
    rendered = render_json(value) + "\n"
    if path == "-":
        sys.stdout.write(rendered)
        return
    target = Path(path)
    _write_create_only(
        target,
        rendered.encode("utf-8"),
        exists_code="controller_output_exists",
        exists_message=f"refusing to overwrite output: {target}",
    )


def _mailbox_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mailbox-repo", type=Path, required=True)
    parser.add_argument("--branch", help="must match the explicit transport policy")
    parser.add_argument("--policy", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local Hand Connect: bounded Controller Adapter over an admitted Git mailbox",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="admit a clean dedicated mailbox clone")
    _mailbox_args(init)

    build = commands.add_parser("build", help="build and validate one Task v1 document")
    build.add_argument("--target-node", required=True)
    build.add_argument("--action", required=True)
    build.add_argument("--params-file", type=Path)
    build.add_argument("--task-id")
    build.add_argument("--output", default="-")

    for name in ("submit", "wait", "call"):
        command = commands.add_parser(name)
        _mailbox_args(command)
        command.add_argument("--task-file", type=Path, required=True)
        if name in ("wait", "call"):
            command.add_argument("--timeout-seconds", type=float, default=120.0)
            command.add_argument("--poll-seconds", type=float, default=2.0)
            command.add_argument("--expected-provenance-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            result = GitMailboxControllerAdapter(
                args.mailbox_repo,
                branch=args.branch,
                policy=load_transport(args.policy),
            ).initialize()
        elif args.command == "build":
            task = build_task(
                args.target_node,
                args.action,
                _params(args.params_file),
                task_id=args.task_id,
            )
            _write_output(args.output, task)
            return 0
        else:
            task = load_task_file(args.task_file)
            adapter = GitMailboxControllerAdapter(
                args.mailbox_repo,
                branch=args.branch,
                policy=load_transport(args.policy),
                expected_provenance=(
                    _expected_provenance(args.expected_provenance_file)
                    if args.command in ("wait", "call")
                    else None
                ),
            )
            if args.command == "submit":
                result = adapter.submit(task)
            elif args.command == "wait":
                result = adapter.wait(
                    task,
                    timeout_seconds=args.timeout_seconds,
                    poll_seconds=args.poll_seconds,
                )
            else:
                result = adapter.call(
                    task,
                    timeout_seconds=args.timeout_seconds,
                    poll_seconds=args.poll_seconds,
                )
        sys.stdout.write(render_json(result) + "\n")
        return 0
    except LocalHandError as exc:
        sys.stderr.write(
            render_json(
                {
                    "operation": getattr(args, "command", "unknown"),
                    "status": exc.status,
                    "error_code": exc.code,
                    "error": exc.message,
                }
            )
            + "\n"
        )
        return 3 if exc.status == "indeterminate" else 2


if __name__ == "__main__":
    raise SystemExit(main())
