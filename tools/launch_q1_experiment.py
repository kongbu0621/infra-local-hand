#!/usr/bin/env python3
"""Bind one existing Q1 controller incarnation and exec the experiment entry.

Requires the administrator's protected launch input, exact bytes digest/source,
prebuilt output parent and independently supervised unit/collectors. Does not
install, start a unit, provision a host, mint a ticket, reset a budget or retry.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys


def _refuse(status, reason, code):
    # No supplied path/ticket or arbitrary exception message reaches stdout.
    raw = (json.dumps({"schema": "local-hand-quota-q1-launch/v1", "status": status,
                       "failure_code": reason, "evidence_retained": "DO_NOT_RETRY_OR_REPLACE",
                       "admission_proven": False, "real_e3_accepted": False,
                       "production_supported": False}, sort_keys=True, separators=(",", ":")) + "\n").encode()
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(1, raw[offset:])
            if count <= 0:
                return 74
            offset += count
    except OSError:
        return 74
    return code


def main(argv=None):
    if not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        return _refuse("REJECTED", "ISOLATED_PYTHON_REQUIRED", 2)
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--input", required=True, metavar="PROTECTED_ABSPATH")
    parser.add_argument("--sha256", required=True, metavar="SHA256")
    parser.add_argument("--source-commit", required=True, metavar="FULL40")
    args = parser.parse_args(argv)
    if not sys.platform.startswith("linux"):
        return _refuse("UNSUPPORTED", "LINUX_REQUIRED", 3)
    if os.getuid() != 0 or os.geteuid() != 0:
        return _refuse("REJECTED", "ADMIN_CONTROLLER_REQUIRED", 2)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from admin.local_hand_quota_observer.admission import Rejected
    from admin.local_hand_quota_observer.launcher import launch_experiment
    try:
        launch_experiment(args.input, args.sha256, args.source_commit,
                          launcher_path=os.path.abspath(__file__))
    except Rejected as error:
        reason = str(error)
        reason = reason if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", reason) else "LAUNCH_REJECTED"
        return _refuse("REJECTED", reason, 2)
    except (Exception, KeyboardInterrupt):
        return _refuse("UNKNOWN", "LAUNCH_IO_OR_EXEC_UNCERTAIN", 4)
    return _refuse("UNKNOWN", "EXEC_RETURNED", 4)


if __name__ == "__main__":
    raise SystemExit(main())
