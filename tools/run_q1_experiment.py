#!/usr/bin/env python3
"""One explicitly pinned Q1 admin experiment, inside its prepared supervisor.

No installation, host provisioning, listener, retry, reset, or production support.
Use python -I -B and the exact private input file/digest/source commit supplied
by the fixture administrator. The operation and ORIGINAL ticket live in that
protected file. Diagnostic stdout is private and bounded, not a Q2 receipt.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def _refusal(status, code):
    # Platform/flag rejection must precede importing any repository runtime.
    return (json.dumps({"schema": "local-hand-quota-q1-experiment/v1", "status": status,
                       "failure_code": code, "controller_entered": False,
                       "admission_proven": False, "real_e3_accepted": False,
                       "production_supported": False}, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write(raw):
    # Output may block: only the already-prepared outer supervisor can bound it.
    # A transport failure never causes another query or a second success record.
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(1, raw[offset:offset + 4096])
            if count <= 0:
                return False
            offset += count
        return True
    except OSError:
        return False


def main(argv=None):
    if not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        return 2 if _write(_refusal("REJECTED", "ISOLATED_PYTHON_REQUIRED")) else 74
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--input", required=True, metavar="PROTECTED_ABSPATH")
    parser.add_argument("--sha256", required=True, metavar="SHA256")
    parser.add_argument("--source-commit", required=True, metavar="FULL40")
    args = parser.parse_args(argv)
    if not sys.platform.startswith("linux"):
        return 3 if _write(_refusal("UNSUPPORTED", "LINUX_REQUIRED")) else 74
    if os.getuid() != 0 or os.geteuid() != 0:
        return 2 if _write(_refusal("REJECTED", "ADMIN_CONTROLLER_REQUIRED")) else 74
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from admin.local_hand_quota_observer.experiment import execute_experiment
    raw = execute_experiment(args.input, args.sha256, args.source_commit)
    if not _write(raw):
        return 74
    return {"OBSERVED": 0, "REJECTED": 2, "UNSUPPORTED": 3, "UNKNOWN": 4}[json.loads(raw)["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
