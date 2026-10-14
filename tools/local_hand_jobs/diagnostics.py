"""Private failure locations without exception messages, payloads or credentials."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import time

from .contract import JobError
from .quota_contract import QuotaError


def failure(component, error, *, operation_id, phase, action, control_started=None):
    causes, seen = [], set()
    while error is not None and id(error) not in seen and len(causes) < 8:
        seen.add(id(error))
        item = {"type": type(error).__name__}
        if isinstance(error, (JobError, QuotaError)) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", error.code):
            item["code"] = error.code
        for name in ("errno", "sqlite_errorcode"):
            value = getattr(error, name, None)
            if type(value) is int:
                item[name] = value
        frames, tb = [], error.__traceback__
        while tb is not None:
            frames.append({"file": Path(tb.tb_frame.f_code.co_filename).name,
                           "function": tb.tb_frame.f_code.co_name, "line": tb.tb_lineno})
            tb = tb.tb_next
        item["frames"] = frames[-16:]
        causes.append(item)
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    logging.getLogger("local_hand_jobs." + component).error("execution_failure %s", json.dumps({
        "time_ns": time.time_ns(), "pid": os.getpid(), "operation_id": operation_id,
        "phase": phase, "action": action, "control_started": control_started, "causes": causes,
    }, separators=(",", ":")))
