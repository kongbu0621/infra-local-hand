"""Pure, fail-closed CIFS quota-query contract; no live query authority.

The response grammar is pinned to Samba 4.23.0 source, not inferred from its
manual. All accepted transcripts remain LOGIC_ONLY. No function opens a file,
starts a process, loads credentials, or connects to a NAS. The live entry point
is deliberately unsupported until a supervised, authenticated collector and
the actual writer/quota-domain binding have been admitted.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import PurePosixPath
import re

from .contract import (DIGEST_PATTERN, JobError, MAX_SAFE_INTEGER, REF_PATTERN,
                       UUID4_PATTERN, UUID_PATTERN, canonical_bytes)

PROVIDER = "smbcquotas-user-v1"
SAMBA_VERSION = "4.23.0"
SAMBA_COMMIT = "942092eadf52c46f9bd913525015d53cb1cc8fb1"
SAMBA_SOURCE_BLOBS = {
    "source3/utils/smbcquotas.c": "b9bbb0f01853724d26a67bc321d3a7140e8da313",
    "source3/libsmb/cliquota.c": "865a41ff6188600defd5050c28016bda7a58ed50",
    "source3/include/ntquotas.h": "6fbbbb9ae5f35890018a13dcdc1caf64326963df",
}
MAX_OUTPUT_BYTES = 4096
MAX_QUERY_WINDOW_NS = 30_000_000_000
MAX_OBSERVATION_AGE_NS = 1_000_000_000
_NUMBER = r" *(0|[1-9][0-9]{0,19})"
_FS_RESPONSE = re.compile(
    r"File System QUOTAS:\nLimits:\n Default Soft Limit: " + _NUMBER
    + r"\n Default Hard Limit: " + _NUMBER
    + r"\nQuota Flags:\n Quotas Enabled: (On|Off)\n Deny Disk:      (On|Off)"
    + r"\n Log Soft Limit: (On|Off)\n Log Hard Limit: (On|Off)\n", re.ASCII)
_USER_RESPONSE = re.compile(
    r"Quotas for User: (S-[0-9-]+)\nUsed Space: " + _NUMBER
    + r"\nSoft Limit: " + _NUMBER + r"\nHard Limit: " + _NUMBER + r"\n", re.ASCII)


def _unsupported(message="NAS quota observation is not admitted"):
    # Never include the private mapping, server response, or credentials.
    return JobError("UNSUPPORTED", message)


def _keys(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise _unsupported("NAS quota contract fields are incomplete or ambiguous")


def _match(value, pattern):
    if type(value) is not str or re.fullmatch(pattern, value, re.ASCII) is None:
        raise _unsupported("NAS quota identity is malformed")


def _integer(value, minimum=0, maximum=MAX_SAFE_INTEGER):
    if type(value) is not int or not minimum <= value <= maximum:
        raise _unsupported("NAS quota numeric bound is invalid")
    return value


def _path(value, *, root_allowed=False):
    if (type(value) is not str or len(value) > 1024 or not value.startswith("/")
            or value.startswith("//") or (value == "/" and not root_allowed)
            or str(PurePosixPath(value)) != value or ".." in PurePosixPath(value).parts
            or re.search(r"[^A-Za-z0-9/._-]", value)):
        raise _unsupported("NAS quota path is not canonical")


def _sid(value):
    _match(value, r"S-1-(?:0|[1-9][0-9]{0,14})(?:-(?:0|[1-9][0-9]{0,9})){1,15}")
    parts = value.split("-")
    if int(parts[2]) > 2**48 - 1 or any(int(item) > 2**32 - 1 for item in parts[3:]):
        raise _unsupported("NAS quota SID is out of range")
    return value


def _digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def validate_admission(value):
    """Validate declarations only; these fields cannot prove live enforcement."""
    _keys(value, {"provider", "storage_ref", "resource_id", "quota_domain", "share",
                  "remote_sid", "archive_root", "storage_config_digest", "mount", "tool"})
    if value["provider"] != PROVIDER:
        raise _unsupported("NAS quota provider is unsupported")
    for key in ("storage_ref", "resource_id", "quota_domain"):
        _match(value[key], REF_PATTERN)
    _match(value["share"], r"//[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?/[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
    server = value["share"].split("/")[2]
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
           for label in server.split(".")):
        raise _unsupported("NAS quota server name is not canonical")
    _sid(value["remote_sid"])
    _path(value["archive_root"])
    _match(value["storage_config_digest"], DIGEST_PATTERN)
    mount = value["mount"]
    _keys(mount, {"type", "source", "root", "target", "device", "inode", "mount_id", "namespace"})
    if (mount["type"] != "cifs" or mount["source"] != value["share"]
            or mount["target"] != value["archive_root"]):
        raise _unsupported("NAS quota share and mount are not the same CIFS boundary")
    _path(mount["root"], root_allowed=True)
    for key in ("device", "inode", "mount_id"):
        _integer(mount[key], 0 if key == "device" else 1)
    _match(mount["namespace"], r"mnt:\[[1-9][0-9]{0,19}\]")
    tool = value["tool"]
    _keys(tool, {"path", "sha256", "version", "client_config", "client_config_digest",
                "authentication_file", "credential_ref", "network_boundary_ref"})
    for key in ("path", "client_config", "authentication_file"):
        _path(tool[key])
        if tool[key] == value["archive_root"] or tool[key].startswith(value["archive_root"] + "/"):
            raise _unsupported("Quota query inputs cannot come from the observed archive")
    if len({tool[key] for key in ("path", "client_config", "authentication_file")}) != 3:
        raise _unsupported("Quota query input roles cannot alias")
    for key in ("sha256", "client_config_digest"):
        _match(tool[key], DIGEST_PATTERN)
    for key in ("credential_ref", "network_boundary_ref"):
        _match(tool[key], REF_PATTERN)
    if tool["version"] != SAMBA_VERSION:
        raise _unsupported("Quota query output version is not pinned")
    return copy.deepcopy(value)


def _context(value):
    _keys(value, {"operation_id", "execution_id", "phase", "boot_id", "nas_bytes",
                  "not_before_boottime_ns", "deadline_boottime_ns"})
    _match(value["operation_id"], UUID4_PATTERN)
    _match(value["boot_id"], UUID_PATTERN)
    if (value["phase"] not in ("preflight", "business")
            or value["execution_id"] != "job-" + value["operation_id"] + "-" + value["phase"]):
        raise _unsupported("Quota queries belong to another execution phase")
    _integer(value["nas_bytes"], 1)
    start = _integer(value["not_before_boottime_ns"])
    end = _integer(value["deadline_boottime_ns"])
    if not 0 < end - start <= MAX_QUERY_WINDOW_NS:
        raise _unsupported("Quota query window is not finite")
    return copy.deepcopy(value)


def build_query_requests(admission, context):
    """Build exactly two read-only requests; returned argv is NOT executable authority.

    A future collector must prove binary/config bytes, credential isolation,
    authenticated query identity and restricted networking before using these.
    No inherited environment, user-provided options, shell or mutation exists.
    """
    admitted, context = validate_admission(admission), _context(context)
    tool = admitted["tool"]
    prefix = [tool["path"], admitted["share"], "--numeric", "--verbose", "--debuglevel=0",
              "--configfile=" + tool["client_config"],
              "--authentication-file=" + tool["authentication_file"],
              "--client-protection=encrypt", "--use-kerberos=off"]
    requests = []
    for query, option in (("filesystem", "--fs"), ("user", "--quota-user=" + admitted["remote_sid"])):
        item = {"provider": PROVIDER, "query": query, "admission_digest": _digest(admitted),
                "context": copy.deepcopy(context), "argv": prefix + [option],
                "environment": {"LC_ALL": "C", "LANG": "C"}, "stdin": "DEVNULL",
                "max_output_bytes": MAX_OUTPUT_BYTES}
        item["request_digest"] = _digest(item)
        requests.append(item)
    return requests


def _response(raw, expression):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_OUTPUT_BYTES:
        raise _unsupported("Quota query output is absent or exceeds its bound")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise _unsupported("Quota query output is not the pinned numeric format") from None
    match = expression.fullmatch(text)
    if match is None:
        raise _unsupported("Quota query output is incomplete or ambiguous")
    return match.groups()


def parse_filesystem_response(raw):
    """Parse the exact numeric, verbose FS response, rejecting default sentinels."""
    soft, hard, enabled, deny, log_soft, log_hard = _response(raw, _FS_RESPONSE)
    soft, hard = _integer(int(soft), 1), _integer(int(hard), 1)
    if soft > hard or enabled != "On" or deny != "On":
        raise _unsupported("Server quota hard enforcement is absent or inconsistent")
    return {"default_soft_bytes": soft, "default_hard_bytes": hard,
            "quotas_enabled": enabled, "deny_disk": deny,
            "log_soft_limit": log_soft, "log_hard_limit": log_hard}


def parse_user_response(raw, *, remote_sid, nas_bytes):
    """The whole domain hard cap, not available capacity, must fit this job."""
    _sid(remote_sid)
    _integer(nas_bytes, 1)
    sid, used, soft, hard = _response(raw, _USER_RESPONSE)
    if _sid(sid) != remote_sid:
        raise _unsupported("Quota response belongs to another remote identity")
    used, soft, hard = _integer(int(used)), _integer(int(soft), 1), _integer(int(hard), 1)
    if not used <= hard <= nas_bytes or soft > hard:
        raise _unsupported("Quota domain hard limit does not fit the job NAS budget")
    return {"remote_sid": sid, "used_bytes": used, "soft_bytes": soft, "hard_bytes": hard}


def validate_responses(admission, context, observations, *, now):
    """Validate bounded transcripts with before/after bindings; never authorize I/O.

    Each supplied binding is a full admission-shaped observation. Equality and
    freshness catch drift represented by the transcript, but cannot prove that
    an observer or a configured writer SID is trustworthy, nor exclude ABA.
    """
    admitted, context = validate_admission(admission), _context(context)
    requests = build_query_requests(admitted, context)
    _keys(now, {"boot_id", "boottime_ns"})
    _integer(now["boottime_ns"])
    if now["boot_id"] != context["boot_id"] or now["boottime_ns"] > context["deadline_boottime_ns"]:
        raise _unsupported("Quota observations belong to an expired or different boot")
    if type(observations) is not list or len(observations) != 2:
        raise _unsupported("Both fixed quota query results are required")
    previous = context["not_before_boottime_ns"]
    parsed, receipts = {}, []
    for request, item in zip(requests, observations):
        _keys(item, {"request_digest", "boot_id", "started_boottime_ns", "finished_boottime_ns",
                     "before", "after", "exit_code", "stdout", "stderr"})
        if (item["request_digest"] != request["request_digest"] or item["boot_id"] != context["boot_id"]
                or type(item["exit_code"]) is not int or item["exit_code"] != 0
                or type(item["stderr"]) is not bytes or item["stderr"] != b""):
            raise _unsupported("Quota query identity, exit, or diagnostic evidence is uncertain")
        for point in ("before", "after"):
            _keys(item[point], {"boottime_ns", "binding"})
            _integer(item[point]["boottime_ns"])
            # Validate separately: Python equality would otherwise accept bool == int.
            if validate_admission(item[point]["binding"]) != admitted:
                raise _unsupported("Quota binding changed across the read-only query")
        start = _integer(item["started_boottime_ns"])
        finish = _integer(item["finished_boottime_ns"])
        if not previous <= item["before"]["boottime_ns"] <= start <= finish <= item["after"]["boottime_ns"] <= now["boottime_ns"]:
            raise _unsupported("Quota query observations are reordered or outside their window")
        if now["boottime_ns"] - item["before"]["boottime_ns"] > MAX_OBSERVATION_AGE_NS:
            raise _unsupported("Quota observations are stale")
        previous = item["after"]["boottime_ns"]
        if request["query"] == "filesystem":
            parsed["filesystem"] = parse_filesystem_response(item["stdout"])
        else:
            parsed["user"] = parse_user_response(item["stdout"], remote_sid=admitted["remote_sid"], nas_bytes=context["nas_bytes"])
        receipt = {key: copy.deepcopy(value) for key, value in item.items() if key not in ("stdout", "stderr")}
        receipt["stdout_sha256"] = hashlib.sha256(item["stdout"]).hexdigest()
        receipts.append(receipt)
    result = {"provider": PROVIDER, "coverage": "LOGIC_ONLY", "business_authorized": False,
              "admission_digest": _digest(admitted), "context": context,
              "validated_responses": parsed, "receipts": receipts}
    result["observation_digest"] = _digest(result)
    return result


def execute_live_queries(admission, context):
    """No boolean/config/transcript can enable the unimplemented live collector."""
    raise _unsupported("NAS live quota query, writer identity and network isolation are not admitted")
