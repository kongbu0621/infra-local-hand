"""Pure receipt checks for the exact two accepted historical H07 events.

No dispatcher, process creation, cgroup operation or live source admission exists
here. Checking supplied bytes does not establish Git ancestry, global run count,
a fresh VM, or permission to execute. The producer integration remains separate.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re
from typing import Any

_spec = importlib.util.spec_from_file_location(
    "h07_continuation_v2_legacy", Path(__file__).with_name("continuation.py"))
assert _spec and _spec.loader
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)

CONTINUATION_A = "eac5e65449e3a4b7083bc91b9123a253e0cb8320"
CONTINUATION_C = "eb96b87343bfa8b74994265d03417e52430a6efd"
SCOPE = "LH-Q2-H07-R2-CONTINUATION-v1"
DECISION = "LH-Q2-H07-R2-CONTINUATION-CLOSURE-20260930-01"
DISPOSITION = "ACCEPTED_EXACT_ROUNDS_1_AND_2_HISTORICAL_UNKNOWN_ONLY"
ROUND3_REASON = "Per-case cgroup generations and retained early-exit diagnostics under LH-Q2-H07-R2-CONTINUATION-v1"
ROUND2_RUN_ID = "36662298613"
ROUND2_COMMIT = "9d8328cf742fa130c265de23b1b9085b9e8a0581"
ROUND2_BOOT_SHA256 = "c8e2c21edb065608daa4fe6580e8ce548ac276dc933174f270f244699fe22a18"
ROUND2_ZIP_SHA256 = "21c2c19d081adb1a89d8b9f2ad62297d86761f88947842705554db70e3c66373"
ROUND2_REPORT_SHA256 = "99d6def38ae46a417a1cfc25b0e6588028813bc0d3b27cee60b083929ad99a54"
DOCUMENT_DIR = "docs/a2-execution/q2-h07-r2-continuation/"
DOCUMENT_HASHES = {
    "REQUIREMENTS.md": "fd45c5f342c249f05958c6f7ef8f80064679623f1c303d0cc127d33716d16159",
    "ARCHITECTURE.md": "da7b6095d5fd1193715349d0c4b85a7777a46f17d6555557cd1593c6787837e6",
    "IMPLEMENTATION_PLAN.md": "c161e4aaa0ecbde1016bc43ea943197ffd087ae14d2463c8536dc07efc17b9d9",
}
PINNED_DOCUMENTS = {**legacy.PINNED_DOCUMENTS,
                    **{DOCUMENT_DIR + k: v for k, v in DOCUMENT_HASHES.items()}}
PINNED_FACTS = {
    **legacy.PINNED_FACTS,
    legacy.ROUND2_RECORD_PATH: "a1591d1f75e4a5b7bd5cf584abe3ba1b4829669387abf8a17b7689b79b0f1a66",
    "docs/governance/Q2_H07_R2_CONTINUATION_OWNER_DECISION.md":
        "9fcab8684f4c21d1b9072fc06dde16b4e627deca71baa83c149682d2a068e8f1",
    "docs/governance/Q2_H07_R2_CONTINUATION_BASELINE.md":
        "7543b8021c72b72dbc8cd53c3b13e03c2dd7ef06801e364432df07405981f735",
}
SOURCE_DIR = "tests/e3_host/spikes/q2_cgroup_fence/"
REQUIRED_SOURCE_PATHS = legacy.REQUIRED_SOURCE_PATHS | set(PINNED_DOCUMENTS) | set(PINNED_FACTS) | {
    SOURCE_DIR + name for name in (
        "helper.c", "run_fixture.py", "verify_receipt.py", "account_evidence.py",
        "continuation_v2.py", "test_continuation_v2.py", "receipt_v3.py", "test_receipt_v3.py",
        "test_fixture_admission.py", "test_verify_receipt.py", "test_account_evidence.py")
} | {".github/workflows/q2-cgroup-fence-spike.yml", "AGENTS.md",
     "docs/governance/Q2_H07_CGROUP_FENCE_SPIKE_OWNER_DECISION.md"}
SOURCE_KEYS = {"expected_commit", "github_sha", "head", "closure_sha256", "approved_A", "closure_C",
               "approved_continuation_A", "closure_continuation_C",
               "approved_r2_continuation_A", "closure_r2_continuation_C"}
KEYS = {"schema_version", "scope", "decision", "approved_continuation_A", "closure_continuation_C",
        "disposition", "prior_records", "used_before", "limit", "current_boot_sha256",
        "prior_boot_sha256", "reason"}


class ContinuationError(ValueError):
    """The exact historical receipt contract is not established."""


def _round_two(record: dict[str, Any]) -> None:
    # The immutable byte pin is decisive. These comparisons also keep the
    # historical meanings explicit, without reclassifying the rejected report.
    okay = (record["run"]["id"] == ROUND2_RUN_ID and record["run"]["attempt"] == 1
            and record["run"]["round"] == 2 and record["source"]["head"] == ROUND2_COMMIT
            and record["artifact"]["id"] == 11074538056
            and record["artifact"]["sha256"] == ROUND2_ZIP_SHA256
            and record["artifact"]["files"]["report.json"]["sha256"] == ROUND2_REPORT_SHA256
            and record["status"] == "UNKNOWN_RETAINED"
            and record["cleanup"]["verified"] is True
            and record["further_dispatch_blocked"] is True
            and record["cases_executed"] == 1
            and record["lab_dispatches_consumed"] == 2 and record["lab_dispatches_limit"] == 3)
    if not okay:
        raise ContinuationError("the accepted round-two historical facts changed")


def validate_continuation(value: Any, *, run: Any, source: Any, provenance: Any) -> list[str]:
    """Check supplied receipt data only; never authorize a dispatch."""
    try:
        if not isinstance(value, dict) or set(value) != KEYS:
            raise ContinuationError("v2 continuation field set")
        expected = {"schema_version": 2, "scope": SCOPE, "decision": DECISION,
                    "approved_continuation_A": CONTINUATION_A, "closure_continuation_C": CONTINUATION_C,
                    "disposition": DISPOSITION, "used_before": 2, "limit": 3, "reason": ROUND3_REASON}
        if any(value[k] != v or type(value[k]) is not type(v) for k, v in expected.items()):
            raise ContinuationError("v2 approval, reason or fixed quota mismatch")
        if (not isinstance(run, dict) or set(run) != {"id", "attempt", "round"}
                or not isinstance(run["id"], str) or not re.fullmatch(r"[1-9][0-9]{0,18}", run["id"])
                or run["id"] in {legacy.ROUND1_RUN_ID, ROUND2_RUN_ID}
                or type(run["attempt"]) is not int or run["attempt"] != 1
                or type(run["round"]) is not int or run["round"] != 3):
            raise ContinuationError("only a distinct final round three attempt one is representable")
        if not isinstance(source, dict) or set(source) != SOURCE_KEYS:
            raise ContinuationError("v2 source field set")
        pins = {"approved_A": legacy.APPROVED_A, "closure_C": legacy.CLOSURE_C,
                "approved_continuation_A": legacy.APPROVED_CONTINUATION_A,
                "closure_continuation_C": legacy.CLOSURE_CONTINUATION_C,
                "approved_r2_continuation_A": CONTINUATION_A,
                "closure_r2_continuation_C": CONTINUATION_C}
        if any(source[k] != v for k, v in pins.items()):
            raise ContinuationError("old and new authority identities must all match")
        heads = [source[k] for k in ("expected_commit", "github_sha", "head")]
        if not all(legacy._hex(v, 40) for v in heads) or len(set(heads)) != 1:
            raise ContinuationError("exact source identities disagree")
        closure = source["closure_sha256"]
        if (not isinstance(closure, dict) or not REQUIRED_SOURCE_PATHS <= closure.keys()
                or len(closure) > 64 or any(not isinstance(p, str) or not p or p.startswith("/")
                                           or any(part in ("", ".", "..") for part in p.split("/"))
                                           or not legacy._hex(h) for p, h in closure.items())):
            raise ContinuationError("required bounded source closure missing or invalid")
        if any(closure.get(p) != h for p, h in {**PINNED_DOCUMENTS, **PINNED_FACTS}.items()):
            raise ContinuationError("immutable documents or historical facts changed")
        records = value["prior_records"]
        if not isinstance(records, list) or len(records) != 2:
            raise ContinuationError("both and only the preceding consumed rounds are required")
        first = legacy._bound_record(records[0], legacy.ROUND1_RECORD_PATH, closure)
        legacy._round1(first)
        second = legacy._bound_record(records[1], legacy.ROUND2_RECORD_PATH, closure)
        _round_two(second)
        prior = [legacy.ROUND1_BOOT_SHA256, ROUND2_BOOT_SHA256]
        if not isinstance(provenance, dict):
            raise ContinuationError("boot provenance missing")
        current = legacy.boot_sha256(provenance.get("boot_id"))
        if (value["prior_boot_sha256"] != prior or value["current_boot_sha256"] != current
                or current in prior):
            raise ContinuationError("boot comparison missing, changed or reused")
    except (ContinuationError, legacy.ContinuationError, KeyError, TypeError, ValueError,
            UnicodeError, RecursionError) as exc:
        return [str(exc)]
    return []


def build_continuation(repo: Path, *, run: dict[str, Any], source: dict[str, Any],
                       provenance: dict[str, Any], reason: str) -> dict[str, Any]:
    """Read only the two fixed public indexes and check the resulting envelope.

    This convenience reader does not invoke a fixture or check live eligibility.
    """
    value = {"schema_version": 2, "scope": SCOPE, "decision": DECISION,
             "approved_continuation_A": CONTINUATION_A, "closure_continuation_C": CONTINUATION_C,
             "disposition": DISPOSITION, "used_before": 2, "limit": 3,
             "reason": reason, "prior_boot_sha256": [legacy.ROUND1_BOOT_SHA256, ROUND2_BOOT_SHA256],
             "current_boot_sha256": legacy.boot_sha256(provenance.get("boot_id")),
             "prior_records": [legacy._read_record(repo, legacy.ROUND1_RECORD_PATH),
                               legacy._read_record(repo, legacy.ROUND2_RECORD_PATH)]}
    errors = validate_continuation(value, run=run, source=source, provenance=provenance)
    if errors:
        raise ContinuationError("; ".join(errors))
    return value
