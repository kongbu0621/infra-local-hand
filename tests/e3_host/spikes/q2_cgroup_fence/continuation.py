"""Pure, source-bound admission for the one approved historical H07 exception.

This record cannot prove the executor's live, repository-wide dispatch count.
The executor must inspect every related run/attempt before each manual dispatch.
No API here creates accounts, launches a probe, contacts GitHub, or dispatches.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
from typing import Any

APPROVED_A = "71c7e842c724650a0e949a63bb898699b41107be"
CLOSURE_C = "8deeed492edeb7e5fa79cbe95c123a27e69f9f92"
APPROVED_CONTINUATION_A = "a08a5055c35009a896ad6c6059d709758cc78436"
CLOSURE_CONTINUATION_C = "7d33c698ff6c1bf34733ee2429d0404ace2abd55"
CONTINUATION_A = APPROVED_CONTINUATION_A
CONTINUATION_C = CLOSURE_CONTINUATION_C
SCOPE = "LH-Q2-H07-R1-CONTINUATION-v1"
DECISION = "LH-Q2-H07-R1-CONTINUATION-CLOSURE-20260929-01"
DISPOSITION = "ACCEPTED_HISTORICAL_UNKNOWN_ONLY"
DOCUMENT_DIR = "docs/a2-execution/q2-h07-r1-continuation/"
DOCUMENT_HASHES = {
    "REQUIREMENTS.md": "74ad594f4446cdf49c4b8d72ff4e5ffb3bd411780e91eeee5a130e58d03eb7f2",
    "ARCHITECTURE.md": "18a248d9398f73405e8836a9586e9c98b8ed9aab2c71242ecdc1c8eaa3823e2b",
    "IMPLEMENTATION_PLAN.md": "9c5726f80f4cb779f658b4d075ee50568ff9818b9f49814e57de71c07aedbe2b",
}
CONTINUATION_DOCUMENTS = {DOCUMENT_DIR + key: value for key, value in DOCUMENT_HASHES.items()}
OLD_DOCUMENT_DIR = "docs/a2-execution/q2-h07-cgroup-fence-spike/"
OLD_DOCUMENT_HASHES = {
    "REQUIREMENTS.md": "41706c5b07cfceea319f10dcab1fcc8b2606995b029566f3e13bb00e41affd51",
    "ARCHITECTURE.md": "6b7ef2487658e759df565084393e5de010db8f35de4966a4790320eea060116c",
    "IMPLEMENTATION_PLAN.md": "0bd3dab26e10e2fa9717ef218fa70846cf5ad3b5888ad2f17596c7b7b385e99d",
}
CONTINUATION_DECISION_PATH = "docs/governance/Q2_H07_R1_CONTINUATION_OWNER_DECISION.md"
CONTINUATION_BASELINE_PATH = "docs/governance/Q2_H07_R1_CONTINUATION_BASELINE.md"
EVIDENCE_DIR = "docs/a2-execution/evidence/q2-h07-cgroup-fence-spike/"
ROUND1_RECORD_PATH = EVIDENCE_DIR + "round-1-verification.json"
ROUND2_RECORD_PATH = EVIDENCE_DIR + "round-2-verification.json"
ROUND1_REPAIR_CI_PATH = EVIDENCE_DIR + "round-1-repair-ci.json"
ROUND1_RECORD_HASH = "821668e202cd0919a68b2407ddc8b0628ed308b28c6e48eb8d5a195139408bdb"
ROUND1_BOOT_SHA256 = "8c0a15a1229a2c1b468cacda35de76f8e9b9fb0f96b82695207da8090a562810"
ROUND1_RUN_ID = "36577764454"
ROUND1_COMMIT = "6b085d9ceb536b9785ea683cd108e92cd8a4eec4"
ROUND1_ARTIFACT_ID = 11038133434
ROUND1_ZIP_SHA256 = "5a48b64ae1a4c38e2ff33aca7d2c47b046acfb2f1232778d527e852f5e307a8e"
ROUND1_REPORT_SHA256 = "9799682e04878ce583a6e446003f8d2e9fd49559adb1cc85b3bf6c650b5a013b"
ROUND2_REASON = "Account profile and bounded account evidence repair under LH-Q2-H07-R1-CONTINUATION-v1"
PINNED_FACTS = {
    ROUND1_RECORD_PATH: ROUND1_RECORD_HASH,
    ROUND1_REPAIR_CI_PATH: "9752e58e63a3612082d52ed1b51535ba3a64fab7bc71e99bde0348e2f2beae83",
    CONTINUATION_DECISION_PATH: "79525c8031c5a1f2b304df4f416ac35b34481b1677c9dc40cd1523d46a098162",
}
PINNED_DOCUMENTS = {**{OLD_DOCUMENT_DIR + k: v for k, v in OLD_DOCUMENT_HASHES.items()},
                    **{DOCUMENT_DIR + k: v for k, v in DOCUMENT_HASHES.items()}}
REQUIRED_SOURCE_PATHS = set(PINNED_DOCUMENTS) | set(PINNED_FACTS) | {
    CONTINUATION_BASELINE_PATH,
    "tests/e3_host/spikes/q2_cgroup_fence/continuation.py",
    "tests/e3_host/spikes/q2_cgroup_fence/test_continuation.py",
}
MAX_BYTES = 2 * 1024 * 1024
REPAIRABLE_SOURCE_PATHS = {
    "tests/e3_host/spikes/q2_cgroup_fence/" + name for name in
    ("run_fixture.py", "verify_receipt.py", "account_evidence.py", "continuation.py")
} | {".github/workflows/q2-cgroup-fence-spike.yml"}
KEYS = {"schema_version", "scope", "decision", "approved_continuation_A",
        "closure_continuation_C", "disposition", "prior_records", "used_before",
        "limit", "current_boot_sha256", "prior_boot_sha256", "reason"}


class ContinuationError(ValueError):
    """A missing or contradictory historical fact prevents continuation."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hex(value: Any, size: int = 64) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % size, value) is not None


def _reason(value: Any) -> bool:
    return (isinstance(value, str) and 1 <= len(value.encode("utf-8")) <= 512 and
            not any(ord(char) < 32 for char in value))


def boot_sha256(value: Any) -> str:
    """Hash exactly the canonical lowercase boot UUID, without a newline."""
    if not isinstance(value, str) or not re.fullmatch(
            r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", value):
        raise ContinuationError("boot identity missing or noncanonical")
    return _sha(value.encode("ascii"))


def _json(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_BYTES:
        raise ContinuationError("prior original exceeds report evidence budget")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ContinuationError("duplicate key in prior original")
            result[key] = value
        return result

    def constant(_: str) -> None:
        raise ContinuationError("nonfinite prior original")

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError) as exc:
        raise ContinuationError("invalid prior original JSON") from exc
    if not isinstance(value, dict):
        raise ContinuationError("prior original must be an object")
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > 24 or count > 40000:
            raise ContinuationError("prior original structure exceeds limits")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
    return value


def _read_record(repo: Path, path: str) -> dict[str, Any]:
    target = repo / path
    if target.is_symlink() or not target.is_file():
        raise ContinuationError("missing regular prior verification index: " + path)
    try:
        with target.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ContinuationError("prior index exceeds report evidence budget")
        content = raw.decode("utf-8", "strict")
    except (OSError, UnicodeError) as exc:
        raise ContinuationError("unreadable prior verification index") from exc
    return {"path": path, "sha256": _sha(raw), "bytes": len(raw), "content": content}


def _bound_record(value: Any, path: str, closure: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"path", "sha256", "bytes", "content"}:
        raise ContinuationError("prior record field set")
    if value["path"] != path or type(value["bytes"]) is not int:
        raise ContinuationError("prior record identity/size")
    if not isinstance(value["content"], str):
        raise ContinuationError("prior record original bytes missing")
    raw = value["content"].encode("utf-8")
    if (len(raw) != value["bytes"] or len(raw) > MAX_BYTES or
            not _hex(value["sha256"]) or _sha(raw) != value["sha256"] or
            closure.get(path) != value["sha256"]):
        raise ContinuationError("prior record original/source closure digest mismatch")
    return _json(value["content"])


def _round1(record: dict[str, Any]) -> None:
    # The exact byte pin above is decisive; these checks make the exception's
    # unchanged factual meaning explicit rather than converting it to success.
    try:
        okay = (record["schema_version"] == 1 and record["run"]["id"] == ROUND1_RUN_ID and
                record["run"]["attempt"] == 1 and record["run"]["round"] == 1 and
                record["source"]["head"] == ROUND1_COMMIT and
                record["artifact"]["id"] == ROUND1_ARTIFACT_ID and
                record["artifact"]["sha256"] == ROUND1_ZIP_SHA256 and
                record["artifact"]["files"]["report.json"]["sha256"] == ROUND1_REPORT_SHA256 and
                record["status"] == "UNKNOWN_RETAINED" and
                record["cleanup"]["verified"] is False and
                record["capability_executed"] is False and record["cases_executed"] == 0 and
                record["case_statuses"] == {f"C{i}": "NOT_RUN" for i in range(1, 7)} and
                record["lab_dispatches_consumed"] == 1 and record["lab_dispatches_limit"] == 3)
    except (KeyError, TypeError):
        okay = False
    if not okay:
        raise ContinuationError("the approved round-one historical unknown was altered")


def _receipt_verifier() -> Any:
    # Delayed import avoids a module cycle: schema-2 receipt validation imports
    # this module; a round-3 check independently validates a schema-2 round-2
    # report whose own continuation contains only the fixed first-round index.
    spec = importlib.util.spec_from_file_location(
        "h07_continuation_prior_receipt", Path(__file__).with_name("verify_receipt.py"))
    if spec is None or spec.loader is None:
        raise ContinuationError("independent prior receipt verifier unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _round2(record: dict[str, Any], source: dict[str, Any], reason: str) -> tuple[str, str]:
    """Read a future reviewed index, never a caller's 'previous safe' boolean.

    The index retains the original report string and its digest. A future index
    must be committed into the current exact source closure before round 3.
    A qualified, unsupported, inconclusive (including C5 race fishing), newly
    unknown, malformed, or incompletely cleaned second round cannot continue.
    """
    keys = {"schema_version", "execution_kind", "run", "artifact", "original_report",
            "lab_dispatches_consumed", "lab_dispatches_limit", "workflow_runs", "next_repair"}
    if set(record) != keys or type(record["schema_version"]) is not int or record["schema_version"] != 2:
        raise ContinuationError("round-two verification index schema")
    run = record["run"]
    if (record["execution_kind"] != "real_hosted_lab_round_review" or
            not isinstance(run, dict) or set(run) != {"id", "attempt", "round"} or
            not isinstance(run["id"], str) or not re.fullmatch(r"[1-9][0-9]{0,19}", run["id"]) or
            run["id"] == ROUND1_RUN_ID or type(run["attempt"]) is not int or run["attempt"] != 1 or
            type(run["round"]) is not int or run["round"] != 2 or
            type(record["lab_dispatches_consumed"]) is not int or record["lab_dispatches_consumed"] != 2 or
            type(record["lab_dispatches_limit"]) is not int or record["lab_dispatches_limit"] != 3):
        raise ContinuationError("round-two run/quota identity")
    inventory = record["workflow_runs"]
    expected_inventory = [{"id": ROUND1_RUN_ID, "attempt": 1, "round": 1}, run]
    if (inventory != expected_inventory or not isinstance(inventory, list) or
            any(not isinstance(row, dict) or type(row.get("attempt")) is not int or
                type(row.get("round")) is not int for row in inventory)):
        raise ContinuationError("all preceding consumed runs must be retained in order")
    artifact = record["artifact"]
    if (not isinstance(artifact, dict) or set(artifact) != {"id", "sha256", "report_sha256"} or
            type(artifact["id"]) is not int or artifact["id"] <= 0 or
            not _hex(artifact["sha256"]) or not _hex(artifact["report_sha256"]) or
            not isinstance(record["original_report"], str) or
            _sha(record["original_report"].encode("utf-8")) != artifact["report_sha256"]):
        raise ContinuationError("round-two original artifact/report binding")
    report = _json(record["original_report"])
    if report.get("schema_version") != 2 or report.get("run") != run:
        raise ContinuationError("round-two original report version/run mismatch")
    verifier = _receipt_verifier()
    result = verifier.derive_report(report)
    if (result.get("errors") or result.get("status") != "REJECTED" or
            report.get("status") != "REJECTED" or report.get("cleanup", {}).get("verified") is not True or
            any(not row.get("case_expectation_met") for row in result.get("case_results", []))):
        raise ContinuationError("round two is qualified or retains a new blocking result")
    if report.get("capability") is not None and not verifier.derive_capability(report["capability"])["supported"]:
        raise ContinuationError("round two retains unsupported capability")
    repair = record["next_repair"]
    repair_keys = {"reason", "defect", "commit", "changed_source_sha256", "offline_checks", "ordinary_ci"}
    if (not isinstance(repair, dict) or set(repair) != repair_keys or
            not _reason(repair["reason"]) or repair["reason"] != reason or reason == ROUND2_REASON or
            not _reason(repair["defect"]) or not _hex(repair["commit"], 40)):
        raise ContinuationError("a separate definite source repair reason is required")
    changes = repair["changed_source_sha256"]
    if not isinstance(changes, dict) or not changes or len(changes) > 16:
        raise ContinuationError("repaired source bytes missing")
    previous_closure = report.get("source", {}).get("closure_sha256", {})
    for path, hashes in changes.items():
        if (not isinstance(path, str) or path not in REPAIRABLE_SOURCE_PATHS or
                not isinstance(hashes, dict) or set(hashes) != {"before", "after"} or
                not _hex(hashes["before"]) or not _hex(hashes["after"]) or
                hashes["before"] == hashes["after"] or previous_closure.get(path) != hashes["before"] or
                source["closure_sha256"].get(path) != hashes["after"]):
            raise ContinuationError("repair does not bind changed experiment source bytes")
    checks = repair["offline_checks"]
    if not isinstance(checks, list) or not 1 <= len(checks) <= 16:
        raise ContinuationError("repair offline verification missing")
    for check in checks:
        if (not isinstance(check, dict) or set(check) != {"command", "exit_code", "log_sha256"} or
                not _reason(check["command"]) or type(check["exit_code"]) is not int or
                check["exit_code"] != 0 or not _hex(check["log_sha256"])):
            raise ContinuationError("repair offline verification incomplete")
    ci = repair["ordinary_ci"]
    if (not isinstance(ci, dict) or set(ci) != {"id", "attempt", "head_sha", "conclusion"} or
            not isinstance(ci["id"], str) or not re.fullmatch(r"[1-9][0-9]{0,19}", ci["id"]) or
            type(ci["attempt"]) is not int or ci["attempt"] != 1 or ci["head_sha"] != repair["commit"] or
            ci["conclusion"] != "success"):
        raise ContinuationError("repair ordinary CI identity/result incomplete")
    return run["id"], boot_sha256(report.get("provenance", {}).get("boot_id"))


def validate_continuation(value: Any, *, run: Any, source: Any, provenance: Any) -> list[str]:
    """Validate retained facts only; never infer global quota from a round input."""
    try:
        if not isinstance(value, dict) or set(value) != KEYS:
            raise ContinuationError("continuation field set")
        expected = {"schema_version": 1, "scope": SCOPE, "decision": DECISION,
                    "approved_continuation_A": APPROVED_CONTINUATION_A,
                    "closure_continuation_C": CLOSURE_CONTINUATION_C,
                    "disposition": DISPOSITION, "limit": 3}
        if any(value[key] != item or type(value[key]) is not type(item) for key, item in expected.items()):
            raise ContinuationError("continuation approval/disposition identity")
        if (not isinstance(run, dict) or set(run) != {"id", "attempt", "round"} or
                not isinstance(run["id"], str) or not re.fullmatch(r"[1-9][0-9]{0,19}", run["id"]) or
                run["id"] == ROUND1_RUN_ID or type(run["attempt"]) is not int or run["attempt"] != 1 or
                type(run["round"]) is not int or run["round"] not in (2, 3) or
                type(value["used_before"]) is not int or value["used_before"] != run["round"] - 1):
            raise ContinuationError("continuation round/attempt/consumed quota")
        if not isinstance(source, dict):
            raise ContinuationError("continuation source missing")
        for key, pin in (("approved_A", APPROVED_A), ("closure_C", CLOSURE_C),
                         ("approved_continuation_A", APPROVED_CONTINUATION_A),
                         ("closure_continuation_C", CLOSURE_CONTINUATION_C)):
            if source.get(key) != pin:
                raise ContinuationError("continuation source old/new A/C mismatch")
        heads = [source.get(key) for key in ("expected_commit", "github_sha", "head")]
        if not all(_hex(head, 40) for head in heads) or len(set(heads)) != 1:
            raise ContinuationError("continuation exact D mismatch")
        closure = source.get("closure_sha256")
        if not isinstance(closure, dict) or not REQUIRED_SOURCE_PATHS <= closure.keys():
            raise ContinuationError("continuation source closure lacks mandatory facts")
        if len(closure) > 64 or any(not isinstance(path, str) or path.startswith("/") or
                                    ".." in path.split("/") or not _hex(pin)
                                    for path, pin in closure.items()):
            raise ContinuationError("continuation source closure path/digest")
        if any(closure.get(path) != pin for path, pin in {**PINNED_DOCUMENTS, **PINNED_FACTS}.items()):
            raise ContinuationError("continuation pinned documents/historical facts changed")
        if not _reason(value["reason"]):
            raise ContinuationError("continuation repair reason missing")
        records = value["prior_records"]
        if not isinstance(records, list) or len(records) != run["round"] - 1:
            raise ContinuationError("every preceding consumed round requires original evidence")
        record1 = _bound_record(records[0], ROUND1_RECORD_PATH, closure)
        _round1(record1)
        previous_boots = [ROUND1_BOOT_SHA256]
        if run["round"] == 2:
            if value["reason"] != ROUND2_REASON:
                raise ContinuationError("round two requires the reviewed account/evidence repair reason")
        else:
            record2 = _bound_record(records[1], ROUND2_RECORD_PATH, closure)
            previous_id, previous_boot = _round2(record2, source, value["reason"])
            if run["id"] == previous_id:
                raise ContinuationError("a previous run cannot be reused")
            previous_boots.append(previous_boot)
        if not isinstance(provenance, dict):
            raise ContinuationError("continuation boot provenance missing")
        boot = boot_sha256(provenance.get("boot_id"))
        if (value["prior_boot_sha256"] != previous_boots or len(set(previous_boots)) != len(previous_boots) or
                value["current_boot_sha256"] != boot or boot in previous_boots):
            raise ContinuationError("boot reuse or incomplete prior boot binding")
    except (ContinuationError, KeyError, TypeError, ValueError, UnicodeError, RecursionError) as exc:
        return [str(exc)]
    return []


def build_continuation(repo: Path, *, run: dict[str, Any], source: dict[str, Any],
                       provenance: dict[str, Any], reason: str) -> dict[str, Any]:
    """Read fixed source-bound history. No arbitrary previous-safe input exists."""
    if type(run.get("round")) is not int or run["round"] not in (2, 3):
        raise ContinuationError("continuation allows only remaining rounds two or three")
    records = [_read_record(repo, ROUND1_RECORD_PATH)]
    prior_boots = [ROUND1_BOOT_SHA256]
    if run["round"] == 3:
        record = _read_record(repo, ROUND2_RECORD_PATH)
        records.append(record)
        # Validate the full second-round original before using any of its facts.
        bound = _bound_record(record, ROUND2_RECORD_PATH, source.get("closure_sha256", {}))
        _, boot = _round2(bound, source, reason)
        prior_boots.append(boot)
    return {"schema_version": 1, "scope": SCOPE, "decision": DECISION,
            "approved_continuation_A": APPROVED_CONTINUATION_A,
            "closure_continuation_C": CLOSURE_CONTINUATION_C, "disposition": DISPOSITION,
            "prior_records": records, "used_before": run["round"] - 1, "limit": 3,
            "current_boot_sha256": boot_sha256(provenance.get("boot_id")),
            "prior_boot_sha256": prior_boots, "reason": reason}


def admit_continuation(repo: Path, *, run: dict[str, Any], source: dict[str, Any],
                       provenance: dict[str, Any], reason: str) -> dict[str, Any]:
    """Build and require the approved local evidence before any fixture effects."""
    value = build_continuation(repo, run=run, source=source, provenance=provenance, reason=reason)
    errors = validate_continuation(value, run=run, source=source, provenance=provenance)
    if errors:
        raise ContinuationError("; ".join(errors))
    return value
