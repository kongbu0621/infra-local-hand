"""Fixed Ledger catalog and immutable server-resolved execution plans.

Lookups are trusted in-process snapshots, never caller paths or storage readers.
Slow byte and mount verification is delegated to registered runner preflight.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Mapping

from .contract import (KINDS, REF_PATTERN, SUITES, JobError, Principal,
                       canonical_bytes, validate_submit)
from .ledger_jobs import (BUILD_REQUIREMENTS, SCRIPT_BLOBS, SOURCE_COMMIT,
                          build_plan, LedgerPlanError)
from .policy import freeze, thaw

PREREQUISITE_MAX_AGE_SECONDS = 24 * 60 * 60
REGISTRY_MANIFEST = {
    "schema_version": "lh-registry-v1", "source_commit": SOURCE_COMMIT,
    "script_blobs": SCRIPT_BLOBS, "build_requirements": list(BUILD_REQUIREMENTS),
    "kinds": list(KINDS), "suites": list(SUITES),
    "prerequisite_max_age_seconds": PREREQUISITE_MAX_AGE_SECONDS,
    "templates": {
        "ledger.test.source": [["-m", "unittest", "discover", "-s", "tests", "-v"],
                                ["-m", "compileall", "-q", "src", "tests", "tools/acceptance"]],
        "a1_resources": ["tests/test_resources.py", "-v"],
        "a1_response_boundaries": ["tests/test_response_boundaries.py", "-v"],
        "a2_snapshot_resources": ["-m", "unittest", "discover", "-s", "tests", "-p", "test_snapshot_resources.py", "-v"],
        "a2_semantic_resources": ["-m", "unittest", "discover", "-s", "tests", "-p", "test_snapshot_semantic_resources.py", "-v"],
        "ledger.test.installed_local": [["-I", "tests/installed_walkthrough.py", "--repo", "{source}"],
            ["-I", "tests/installed_snapshot_walkthrough.py", "--scratch-parent", "{job-parent}", "--source-commit", SOURCE_COMMIT]],
        "ledger.nas.roundtrip": ["-I", "tools/acceptance/a2_nas_exercise.py", "--local-parent", "{job-parent}",
            "--storage-config", "{admitted-config}", "--source-commit", SOURCE_COMMIT, "--wheel", "{admitted-wheel}"],
    },
}
REGISTRY_DIGEST = hashlib.sha256(canonical_bytes(REGISTRY_MANIFEST)).hexdigest()
_BINDINGS = ("source_digest", "wheel_digest", "installed_payload_digest", "runtime_digest", "environment_fingerprint")
_PREREQUISITES = ("host.inspect", "ledger.prepare", "ledger.test.source", *SUITES, "ledger.test.installed_local")


class Registry:
    def __init__(self, *, prepared_lookup: Callable[[str], Mapping | None] | None = None,
                 evidence_lookup: Callable[[Mapping], list[Mapping]] | None = None,
                 clock: Callable[[], float] = time.time):
        self._prepared_lookup, self._evidence_lookup, self._clock = prepared_lookup, evidence_lookup, clock
        self._prepared: dict[str, Mapping] = {}
        self._evidence: dict[str, Mapping] = {}
        self._policies: list[Any] = []
        self._lock = threading.RLock()
        self.digest = REGISTRY_DIGEST

    def register_prepared(self, ref: str, facts: Mapping) -> None:
        """Publish immutable facts only from the broker's successful seal callback."""
        if type(ref) is not str or re.fullmatch(REF_PATTERN, ref) is None:
            raise JobError("INVALID_REQUEST", "Invalid prepared reference")
        facts = thaw(facts)
        if (facts.get("outcome") != "SUCCEEDED" or facts.get("evidence_state") != "SEALED"
                or not facts.get("seal") or not facts.get("owner") or not facts.get("profile_ref")):
            raise JobError("NOT_SEALED", "Only successful sealed preparation can publish a reference")
        self._check_prepared_fact(facts, {"profile_ref": facts["profile_ref"], "expected": facts.get("expected")},
                                 Principal(facts["owner"], frozenset()))
        facts["prepared_ref"] = ref
        with self._lock:
            if ref in self._prepared and thaw(self._prepared[ref]) != facts:
                raise JobError("CONFLICT", "Prepared reference cannot be overwritten")
            self._prepared[ref] = freeze(facts)
            for policy in self._policies:
                policy.register_prepared_reference(ref, owner=facts["owner"], profile_ref=facts["profile_ref"], expected=facts["expected"])

    def register_evidence(self, facts: Mapping) -> None:
        """Append a server-owned prerequisite observation; failed observations matter."""
        item = thaw(facts)
        if not item.get("evidence_id") or not item.get("kind") or not item.get("profile_ref") or not item.get("owner"):
            raise JobError("INVALID_REQUEST", "Prerequisite evidence identity is incomplete")
        if type(item.get("observed_at")) is not int:
            raise JobError("INVALID_REQUEST", "Prerequisite observation time is required")
        if "event_seq" in item and (type(item["event_seq"]) is not int or item["event_seq"] <= 0):
            raise JobError("INVALID_REQUEST", "Prerequisite event sequence must be positive")
        with self._lock:
            old = self._evidence.get(item["evidence_id"])
            if old is not None and thaw(old) != item:
                raise JobError("CONFLICT", "Prerequisite evidence cannot be overwritten")
            self._evidence[item["evidence_id"]] = freeze(item)

    def _prepared_fact(self, ref: str, request: Mapping, principal: Principal | None) -> dict:
        with self._lock:
            fact = self._prepared.get(ref)
        if fact is None and self._prepared_lookup is not None:
            fact = self._prepared_lookup(ref)
        if fact is None:
            raise JobError("NOT_FOUND", "Prepared artifact is not registered")
        return self._check_prepared_fact(thaw(fact), request, principal)

    @staticmethod
    def _check_prepared_fact(fact: dict, request: Mapping, principal: Principal | None) -> dict:
        if principal is None or fact.get("owner") != principal.principal_id or fact.get("profile_ref") != request["profile_ref"]:
            raise JobError("UNAUTHORIZED", "Prepared artifact is not granted to this principal and profile")
        if fact.get("outcome") != "SUCCEEDED" or fact.get("evidence_state") != "SEALED" or not fact.get("seal"):
            raise JobError("NOT_SEALED", "Prepared artifact has no successful durable seal")
        if not isinstance(fact.get("expected"), dict) or fact["expected"] != request["expected"]:
            raise JobError("STALE_DEPLOYMENT", "Prepared artifact admission binding is no longer current")
        bindings = fact.get("bindings", {})
        if not isinstance(bindings, dict):
            raise JobError("NOT_SEALED", "Prepared artifact bindings are incomplete")
        if set(bindings) - {"source_commit", *_BINDINGS}:
            raise JobError("CONFLICT", "Prepared bindings contain non-payload provenance fields")
        # The prepared payload and execution provenance both expose these
        # values. Never let preflight consume one identity while the eventual
        # seal records a different value from the nested binding map.
        for name in ("source_commit", *_BINDINGS):
            if name in fact and name in bindings and fact[name] != bindings[name]:
                raise JobError("CONFLICT", "Prepared artifact has conflicting provenance bindings")
        if fact.get("source_commit", bindings.get("source_commit")) != SOURCE_COMMIT:
            raise JobError("UNSUPPORTED", "Prepared artifact is not the fixed Ledger source")
        for name in _BINDINGS:
            value = bindings.get(name, fact.get(name))
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise JobError("NOT_SEALED", "Prepared artifact binding is incomplete")
            bindings[name] = value
            fact.setdefault(name, value)
        fact["bindings"] = bindings
        fact["source_commit"] = SOURCE_COMMIT
        # These fields are still independently byte-checked by runner preflight.
        for name in ("root", "source_root", "build_python", "runtime_python", "wheel"):
            value = fact.get(name)
            if not isinstance(value, str) or not value.startswith("/") or ".." in Path(value).parts or str(Path(value)) != value:
                raise JobError("NOT_SEALED", "Prepared artifact path binding is incomplete")
            if name != "root" and Path(fact["root"]) not in Path(value).parents:
                raise JobError("NOT_SEALED", "Prepared artifact paths escaped their immutable root")
        if fact.get("source_blobs", {}).get("tools/acceptance/a2_nas_exercise.py") != SCRIPT_BLOBS["tools/acceptance/a2_nas_exercise.py"] or fact.get("source_blobs", {}).get("tests/installed_snapshot_walkthrough.py") != SCRIPT_BLOBS["tests/installed_snapshot_walkthrough.py"]:
            raise JobError("NOT_SEALED", "Prepared artifact trusted script binding is incomplete")
        if not isinstance(fact.get("files"), dict) or not fact["files"] or fact.get("readonly_enforced") is not True:
            raise JobError("NOT_SEALED", "Prepared artifact immutable payload proof is incomplete")
        fact["sealed"] = True
        return fact

    def _prerequisites(self, request: Mapping, prepared: Mapping, principal: Principal) -> list[dict]:
        with self._lock:
            items = [thaw(item) for item in self._evidence.values()]
        if self._evidence_lookup is not None:
            items.extend(thaw(item) for item in self._evidence_lookup(request))
        current = []
        now = self._clock()
        for requirement in _PREREQUISITES:
            matches = [item for item in items
                if item.get("profile_ref") == request["profile_ref"] and item.get("owner") == principal.principal_id
                and (item.get("suite") if item.get("kind") == "ledger.test.resources" else item.get("kind")) == requirement
                and (requirement == "host.inspect" or item.get("prepared_ref") == request["inputs"]["prepared_ref"])]
            if not matches:
                raise JobError("NOT_SEALED", "Required NAS prerequisite evidence is missing", {"requirement": requirement})
            # A new failed/pending observation supersedes an earlier PASS for
            # admission; old evidence remains in the immutable history.
            # The server's global durable sequence outranks its wall clock:
            # clock rollback must not hide a newly recorded failure/pending run.
            latest_time = max((item.get("event_seq", 0), item.get("observed_at", -1)) for item in matches)
            latest = [item for item in matches if (item.get("event_seq", 0), item.get("observed_at", -1)) == latest_time]
            for item in latest:
                if (item.get("outcome") != "SUCCEEDED" or item.get("evidence_state") != "SEALED"
                        or not item.get("seal_digest") or item.get("coverage") not in ("PASS", "LOGIC_ONLY")
                        or item.get("expected") != request["expected"]
                        or not 0 <= now - item["observed_at"] <= PREREQUISITE_MAX_AGE_SECONDS):
                    raise JobError("NOT_SEALED", "Latest NAS prerequisite is not current successful sealed evidence", {"requirement": requirement})
                names = ("environment_fingerprint",) if requirement == "host.inspect" else _BINDINGS
                if any(item.get("bindings", {}).get(name) != prepared["bindings"][name] for name in names):
                    raise JobError("STALE_DEPLOYMENT", "NAS prerequisite candidate or environment differs", {"requirement": requirement})
                if item.get("coverage") == "LOGIC_ONLY" and requirement not in SUITES:
                    raise JobError("NOT_SEALED", "Logic-only evidence cannot satisfy this prerequisite")
            chosen = sorted(latest, key=lambda item: item["evidence_id"])[-1]
            current.append({"requirement": requirement, "evidence_id": chosen["evidence_id"],
                "seal_digest": chosen["seal_digest"], "observed_at": chosen["observed_at"],
                "bindings": chosen["bindings"], "coverage": chosen["coverage"]})
        return current

    def resolve(self, request: Mapping, policy: Any, *, principal: Principal | None = None) -> Mapping:
        request = validate_submit(request)
        if principal is not None:
            policy.authorize(principal, "lh:submit", request=request)
        if request["expected"] != policy.expected(request["profile_ref"]):
            raise JobError("STALE_DEPLOYMENT", "Expected deployment binding no longer matches")
        with self._lock:
            if all(known is not policy for known in self._policies):
                self._policies.append(policy)
                for ref, fact in self._prepared.items():
                    policy.register_prepared_reference(ref, owner=fact["owner"], profile_ref=fact["profile_ref"], expected=fact["expected"])
        profile = thaw(policy.profile(request["profile_ref"]))
        budget = profile["budgets"][request["kind"]]
        profile["budgets"] = budget
        profile["resources"] = profile["resource_ids"]
        inputs, prepared, prerequisites = request["inputs"], None, []
        if request["kind"] == "ledger.prepare":
            try:
                profile["source"] = profile["sources"][inputs["source_ref"]]
                profile["build_cache"] = profile["build_caches"][inputs["build_cache_ref"]]
            except KeyError:
                raise JobError("UNAUTHORIZED", "Build input is not admitted") from None
            source = profile["source"]
            if source["commit"] != SOURCE_COMMIT or any(source["blobs"].get(name) != digest for name, digest in SCRIPT_BLOBS.items()):
                raise JobError("UNSUPPORTED", "Source and trusted scripts differ from the fixed Ledger baseline")
            if not profile["build_cache"]["files"]:
                raise JobError("UNSUPPORTED", "An independently admitted local build cache is required")
        if "prepared_ref" in inputs:
            prepared = self._prepared_fact(inputs["prepared_ref"], request, principal)
        if request["kind"] == "ledger.nas.roundtrip":
            try:
                profile["storage"] = profile["storages"][inputs["storage_ref"]]
            except KeyError:
                raise JobError("UNAUTHORIZED", "Storage reference is not admitted") from None
            if not isinstance(profile["storage"]["stable_mount_binding"], dict):
                raise JobError("UNSUPPORTED", "Stable cross-stage NAS mount binding has not been admitted")
            prerequisites = self._prerequisites(request, prepared, principal)
        try:
            execution = build_plan(request, profile, prepared, prerequisites)
        except (LedgerPlanError, KeyError, TypeError, ValueError):
            raise JobError("UNSUPPORTED", "Admitted inputs cannot resolve the fixed execution plan") from None
        execution["bindings"].update({"expected": request["expected"],
            "local_hand_source_commit": policy.source_commit,
            "local_hand_installed_payload_digest": policy.installed_payload_digest,
            "local_hand_execution_entrypoint": policy.execution_entrypoint})
        if prepared:
            execution["bindings"].update(prepared["bindings"])
        resources = list(profile["resource_ids"])
        if prepared:
            resources.append("prepared-" + hashlib.sha256(prepared["root"].encode()).hexdigest()[:32])
        if "storage" in profile:
            resources.append(profile["storage"]["resource_id"])
        plan = {"schema_version": "lh-resolved-plan-v1", "kind": request["kind"],
            "operation_id": request["operation_id"], "profile_ref": request["profile_ref"],
            "inputs": inputs, "expected": request["expected"], "budgets": budget,
            "resource_ids": sorted(set(resources)), "reservation_bytes": budget["reservation_bytes"],
            "execution": execution, "prerequisites": prerequisites,
            "policy_generation": policy.generation, "registry_digest": REGISTRY_DIGEST}
        plan["plan_digest"] = hashlib.sha256(canonical_bytes(plan)).hexdigest()
        return freeze(plan)


__all__ = ["Registry", "REGISTRY_DIGEST", "REGISTRY_MANIFEST", "SOURCE_COMMIT", "SCRIPT_BLOBS", "thaw"]
