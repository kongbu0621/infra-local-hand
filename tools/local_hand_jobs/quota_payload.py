"""Bounded canonical transport for the isolated Q2 evidence phase.

Historical SQLite timestamps retain their exact finite JSON values. Only the
two fixed event-list locations admit those floats; quota authority stays on
the original integer-only codecs. Compression never increases a reservation.
"""
from __future__ import annotations

import base64
import json
import math
import zlib

from . import bootstrap
from .contract import JobError

MAX_DECODED_BYTES = 2 * 1024 * 1024
MAX_ENCODED_BYTES = bootstrap.MAX_ENCODED_BYTES
BOOTSTRAP_PREFIX = "lhq2-bootstrap-z1:"
PLAN_PREFIX = "lhq2-plan-z1:"
PLAN_SCHEMA = "local-hand-q2-phase-plan/v2"
PROOF_PREFIX = "lhq2-proof-z1:"
PROOF_SCHEMA = "local-hand-q2-ordinary-proof/v1"
SNAPSHOT_KEYS = {"preparation", "observation", "pending", "closed"}


def _invalid(message="Invalid bounded Q2 payload"):
    return JobError("UNSUPPORTED", message)


def _raw(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, RecursionError) as error:
        raise _invalid() from error
    if len(raw) > MAX_DECODED_BYTES:
        raise JobError("LIMIT_EXCEEDED", "Q2 payload exceeds the fixed decoded bound")
    return raw


def _numeric_view(value, prefixes, field):
    def view(item, path=()):
        if len(path) > 24:
            raise _invalid("Q2 payload nesting exceeds its fixed bound")
        if type(item) is dict:
            return {key: view(child, path + (key,)) for key, child in item.items()}
        if type(item) is list:
            return [view(child, path + (index,)) for index, child in enumerate(item)]
        if type(item) is float:
            if (not math.isfinite(item) or (field == "elapsed_seconds" and item < 0)
                    or not any(len(path) == len(prefix) + 2
                    and path[:len(prefix)] == prefix and type(path[-2]) is int
                    and path[-1] == field for prefix in prefixes)):
                raise _invalid("Float lies outside the fixed historical measurement paths")
            return 0
        return item
    return view(value)


def _checked(value, *, payload):
    # Validate through the legacy credential/environment/depth policy, with
    # floats replaced only in this temporary validation view, never in data.
    prefixes = (("execution", "evidence_snapshot", "broker_events"),
                ("execution", "broker_events")) if payload else (("evidence_snapshot", "broker_events"),)
    bootstrap._check_data(_numeric_view(value, prefixes, "observed_at"))
    if type(value) is not dict:
        raise _invalid()
    execution = value.get("execution") if payload else value
    if type(execution) is not dict:
        raise _invalid()
    if payload and (set(value) != {"version", "execution", "allocation", "observation"}
            or type(value["version"]) is not int or value["version"] != 2):
        raise _invalid("Compressed bootstrap requires the exact Q2 envelope")
    if ("evidence_snapshot" in execution or "broker_events" in execution) and execution.get("phase") != "evidence":
        raise _invalid("Historical payload requires the original evidence phase")


def _pack(value, prefix):
    raw = _raw(value)
    encoded = prefix + base64.b64encode(zlib.compress(raw, 9)).decode("ascii")
    if len(encoded) > MAX_ENCODED_BYTES:
        raise JobError("LIMIT_EXCEEDED", "Q2 payload exceeds the fixed encoded bound")
    return encoded


def _unpack(encoded, prefix):
    if (type(encoded) is not str or not encoded.startswith(prefix)
            or len(encoded) > MAX_ENCODED_BYTES):
        raise _invalid("Invalid bounded Q2 encoding")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        compressed = base64.b64decode(encoded[len(prefix):].encode("ascii"), validate=True)
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(compressed, MAX_DECODED_BYTES + 1)
        # No unbounded flush: an incomplete stream, extra stream, or any bytes
        # beyond the first bounded canonical stream are always rejected.
        if (len(raw) > MAX_DECODED_BYTES or not decompressor.eof
                or decompressor.unconsumed_tail or decompressor.unused_data):
            raise ValueError("non-finite compressed envelope")
        value = json.loads(raw.decode("ascii"), object_pairs_hook=pairs,
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
        if _raw(value) != raw or _pack(value, prefix) != encoded:
            raise ValueError("noncanonical encoding")
        return value
    except (ValueError, UnicodeError, RecursionError, zlib.error) as error:
        raise _invalid("Q2 compressed JSON is invalid") from error


def encode_phase_plan(plan):
    _checked(plan, payload=False)
    return {"schema": PLAN_SCHEMA, "encoded_plan": _pack(plan, PLAN_PREFIX)}


def decode_phase_plan(declaration):
    if (type(declaration) is not dict or set(declaration) != {"schema", "encoded_plan"}
            or declaration["schema"] != PLAN_SCHEMA):
        raise _invalid("Unknown Q2 phase-plan declaration")
    value = _unpack(declaration["encoded_plan"], PLAN_PREFIX)
    _checked(value, payload=False)
    return value


def _ordinary(proof):
    if type(proof) is not dict:
        raise _invalid("Original ordinary proof must be an object")
    # Stage elapsed time is reporting data, never a quota/deadline authority.
    # The result reader preserves this original helper measurement as JSON.
    bootstrap._check_data(_numeric_view(proof, (("result", "stages"),), "elapsed_seconds"))


def encode_bridge_value(value):
    """V2 only: leave authority messages strict, wrap the original proof."""
    if type(value) is not dict or set(value) != SNAPSHOT_KEYS or value["pending"] is None:
        return value
    pending = value["pending"]
    if type(pending) is not dict or set(pending) != {"phase", "proof"}:
        raise _invalid("Original pending proof shape changed")
    _ordinary(pending["proof"])
    wrapped = {"schema": PROOF_SCHEMA, "encoded_proof": _pack(pending["proof"], PROOF_PREFIX)}
    return dict(value, pending=dict(pending, proof=wrapped))


def decode_bridge_value(value):
    if type(value) is not dict or set(value) != SNAPSHOT_KEYS or value["pending"] is None:
        return value
    pending = value["pending"]
    if type(pending) is not dict or set(pending) != {"phase", "proof"}:
        raise _invalid("Original pending proof shape changed")
    wrapped = pending["proof"]
    if (type(wrapped) is not dict or set(wrapped) != {"schema", "encoded_proof"}
            or wrapped["schema"] != PROOF_SCHEMA):
        raise _invalid("Unknown ordinary proof transport")
    proof = _unpack(wrapped["encoded_proof"], PROOF_PREFIX)
    _ordinary(proof)
    return dict(value, pending=dict(pending, proof=proof))


def _artifact_budget(value, *, final_raw=None, marker_bytes=0, block_size=4096):
    from . import quota_contract
    execution = value["execution"]
    try:
        limits = execution["budget_grant"]["limits"]
        if execution["budgets"] != limits:
            raise ValueError("original limits changed")
        bound = [limits["temporary_bytes"], limits["reservation_bytes"]]
        evidence = [root for root in value["observation"]["roots"] if root["role"] == "evidence"]
        if len(evidence) != 1:
            raise ValueError("original evidence root missing")
        bound.append(evidence[0]["hard_bytes"])
        if any(type(limit) is not int or limit <= 0 for limit in bound):
            raise ValueError("invalid artifact budget")
        if type(block_size) is not int or not 0 < block_size <= 4096:
            raise ValueError("unsupported artifact block size")
        # Reserve the entire bounded observation, its field wrapper, a full
        # marker block and the project root directory before original launch.
        # This is a debit against the existing limits, never extra capacity.
        logical = (len(_raw(execution)) + quota_contract.RESPONSE_LIMIT + 1024
                   if final_raw is None else len(final_raw))
        rounded = lambda size: ((size + block_size - 1) // block_size) * block_size
        charged = rounded(logical) + (4096 if final_raw is None else rounded(marker_bytes)) + 4096
        if logical > bound[0] or charged > min(bound[1:]):
            raise JobError("LIMIT_EXCEEDED", "Q2 execution plan exceeds its original artifact budget")
    except (KeyError, TypeError, ValueError) as error:
        raise _invalid("Q2 execution plan has no original artifact budget") from error


def encode_bootstrap(value):
    _checked(value, payload=True)
    # Preserve the exact legacy bytes for every already supported Q2 payload.
    try:
        return bootstrap.encode_payload(value)
    except JobError:
        pass
    _artifact_budget(value)
    return _pack(value, BOOTSTRAP_PREFIX)


def requires_extended(value):
    try:
        bootstrap.encode_payload(value)
        return False
    except JobError:
        return True


def check_final_artifact(value, observation, marker, *, block_size):
    """Recheck actual serialization before any bootstrap-owned file writes."""
    from . import quota_contract
    quota_contract._canonical(observation, quota_contract.RESPONSE_LIMIT)
    execution = dict(value["execution"], quota_observation=observation,
                     bootstrap_allocation=value["allocation"])
    raw = _raw(execution)
    _artifact_budget(value, final_raw=raw, marker_bytes=len(marker), block_size=block_size)
    return raw


def decode_bootstrap(encoded):
    value = _unpack(encoded, BOOTSTRAP_PREFIX)
    _checked(value, payload=True)
    _artifact_budget(value)
    if encode_bootstrap(value) != encoded:
        raise _invalid("Q2 payload does not use its canonical transport")
    return value
