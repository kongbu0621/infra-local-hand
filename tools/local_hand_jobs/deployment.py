"""Verify the complete admitted release before opening a broker or listener."""
from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path
import re
import stat

from local_hand import provenance
from local_hand.protocol import LocalHandError

from .contract import JobError


def _entrypoint(value: str | os.PathLike[str]) -> Path:
    try:
        path = Path(value)
        if (not path.is_absolute() or str(path).startswith("//")
                or ".." in path.parts or str(path) != os.fspath(value)):
            raise ValueError
        # resolve() alone would hide a replaced symlink component.
        for parent in reversed(path.parents):
            if not stat.S_ISDIR(parent.lstat().st_mode):
                raise ValueError
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError
        return path
    except (OSError, TypeError, ValueError):
        raise JobError("PROVENANCE_MISMATCH", "Service entrypoint is not an exact regular file") from None


def release_identity(actual_entrypoint: str | os.PathLike[str]) -> dict[str, str]:
    """Read identity from the executing package tree, never a requested root."""
    actual = _entrypoint(actual_entrypoint)
    root = Path(provenance.__file__).absolute().parent.parent
    if actual not in (root / "local_hand_jobs" / "cli.py", root / "local_hand_mcp" / "server.py"):
        raise JobError("PROVENANCE_MISMATCH", "Service entrypoint is outside the fixed release")
    try:
        metadata = provenance.build_metadata()
        if metadata is not None:
            if metadata["artifact_kind"] != "wheel":
                raise JobError("PROVENANCE_MISMATCH", "Job services require a complete release")
            commit = metadata["source_commit"]
        else:
            commit = provenance.source_commit(require_clean=True)
        digest = provenance.full_payload_digest(root)
    except (LocalHandError, OSError, ValueError):
        raise JobError("PROVENANCE_MISMATCH", "Executing release failed source and payload verification") from None
    return {"source_commit": commit, "installed_payload_digest": digest,
            "execution_entrypoint": str(actual)}


def verify_release(*, expected_source_commit: str, expected_payload_digest: str,
                   expected_entrypoint: str, actual_entrypoint: str | os.PathLike[str]) -> dict[str, str]:
    """Bind installed bytes, immutable source identity and the real service file.

    Expected values come only from the protected private admission configuration.
    This check is deliberately before authority locks, workers and network bind.
    There is no permissive runtime mode for an unsupported or drifting release.
    """
    if (type(expected_source_commit) is not str or re.fullmatch(r"[0-9a-f]{40}", expected_source_commit) is None
            or type(expected_payload_digest) is not str or re.fullmatch(r"[0-9a-f]{64}", expected_payload_digest) is None):
        raise JobError("PROVENANCE_MISMATCH", "Admission requires exact source and payload digests")
    expected = _entrypoint(expected_entrypoint)
    identity = release_identity(actual_entrypoint)
    if (not hmac.compare_digest(identity["source_commit"], expected_source_commit)
            or not hmac.compare_digest(identity["installed_payload_digest"], expected_payload_digest)
            or identity["execution_entrypoint"] != str(expected)):
        raise JobError("PROVENANCE_MISMATCH", "Executing release differs from private admission")
    return identity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect the verified installed job service identity")
    parser.add_argument("--service", choices=("broker", "mcp"), required=True)
    args = parser.parse_args(argv)
    root = Path(provenance.__file__).absolute().parent.parent
    entry = root / ("local_hand_jobs/cli.py" if args.service == "broker" else "local_hand_mcp/server.py")
    try:
        print(json.dumps(release_identity(entry), sort_keys=True))
        return 0
    except JobError as exc:
        parser.exit(2, f"{exc.code}: {exc.message}\n")


if __name__ == "__main__":
    raise SystemExit(main())
