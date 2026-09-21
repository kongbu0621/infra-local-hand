"""Render the Windows Local Hand worker runner from one production template."""
from __future__ import annotations

import argparse
from pathlib import Path


def _ps_single_quoted(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def render_windows_runner(
    *,
    home: str,
    worker_root: str,
    profile: str,
    mailbox: str,
    branch: str,
    runtime: str,
    python: str,
    git: str,
    ssh: str,
    commit: str,
    install_instance_id: str,
    mailbox_uses_ssh: bool,
    mailbox_key: str,
    known_hosts: str,
    install_record: str,
) -> str:
    if not mailbox_uses_ssh:
        raise ValueError("Local Hand v0.1 Windows runner requires an SSH mailbox")
    q = _ps_single_quoted
    return "\n".join(
        (
            "$ErrorActionPreference='Stop'",
            f"$env:HOME={q(home)}; $env:USERPROFILE={q(home)}; $env:PYTHONPATH={q(worker_root)}; "
            "$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONNOUSERSITE='1'",
            "$env:LOCAL_HAND_GIT_TIMEOUT_SECONDS='45'; "
            f"$env:LOCAL_HAND_IMPLEMENTATION_COMMIT={q(commit)}; "
            f"$env:LOCAL_HAND_INSTALL_INSTANCE_ID={q(install_instance_id)}; "
            f"$env:LOCAL_HAND_INSTALL_RECORD={q(install_record)}; "
            f"$env:LOCAL_HAND_GIT_EXECUTABLE={q(git)}; "
            f"$env:LOCAL_HAND_SSH_EXECUTABLE={q(ssh)}; "
            f"$env:LOCAL_HAND_MAILBOX_USES_SSH={q('1' if mailbox_uses_ssh else '0')}; "
            f"$env:LOCAL_HAND_MAILBOX_SSH_KEY={q(mailbox_key)}; "
            f"$env:LOCAL_HAND_KNOWN_HOSTS={q(known_hosts)}",
            f"& {q(python)} -m local_hand.worker --profile {q(profile)} "
            f"--mailbox-repo {q(mailbox)} --mailbox-branch {q(branch)} "
            f"--state-root {q(runtime)} --poll-seconds 5",
            "$workerExitCode=$LASTEXITCODE",
            "if($null -eq $workerExitCode){exit 1}",
            "exit [int]$workerExitCode",
            "",
        )
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a Local Hand Windows worker runner")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--worker-root", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--mailbox", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--git", required=True)
    parser.add_argument("--ssh", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--install-instance-id", required=True)
    parser.add_argument("--install-record", required=True)
    parser.add_argument("--mailbox-uses-ssh", choices=("1",), required=True)
    parser.add_argument("--mailbox-key", required=True)
    parser.add_argument("--known-hosts", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    content = render_windows_runner(
        home=args.home,
        worker_root=args.worker_root,
        profile=args.profile,
        mailbox=args.mailbox,
        branch=args.branch,
        runtime=args.runtime,
        python=args.python,
        git=args.git,
        ssh=args.ssh,
        commit=args.commit,
        install_instance_id=args.install_instance_id,
        install_record=args.install_record,
        mailbox_uses_ssh=args.mailbox_uses_ssh == "1",
        mailbox_key=args.mailbox_key,
        known_hosts=args.known_hosts,
    )
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
