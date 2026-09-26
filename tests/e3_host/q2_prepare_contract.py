"""Strict, private input contract for the isolated Q2 preparation entry.

There are no host/account/path/project defaults. Decoding has no host effects.
The seven new quota domains and all other costs remain bounded by the approved
scope; a valid plan is not a prepared fixture or authority to accept Q2.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath as P
import re

SCHEMA = "local-hand-q2-fixture-plan/v1"
SCOPE = "LH-Q2-FIXTURE-PREP-v1"
BASELINE = "2ea59b8d1b262632bae5636938107ef2f002a59b"
LIMIT = 2 * 1024 * 1024
HEX = r"[0-9a-f]{64}"
UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
SYSTEM_PARENTS = ("query", "management", "controller", "supervisor")
TOOLS = ("python", "compiler", "git", "setpriv", "systemctl", "systemd_run", "groupadd", "useradd", "chattr", "setquota", "blkid")
DIRECTORY_ROLES = ("reservation", "state", "authority", "journal", "capture", "declarations", "session", "control",
                   "profile_work", "profile_evidence", "profile_temporary", "store_parent")
CEILINGS = {"installation_bytes": 256 * 1024**2, "state_bytes": 32 * 1024**2,
            "journal_bytes": 64 * 1024**2, "capture_bytes": 64 * 1024**2}


def require(ok, code):
    if not ok:
        raise ValueError(code)


def keys(value, names):
    require(type(value) is dict and set(value) == set(names), "PREPARE_FIELDS")


def number(value, low=0, high=2**63 - 1):
    require(type(value) is int and low <= value <= high, "PREPARE_INTEGER")
    return value


def token(value, pattern):
    require(type(value) is str and re.fullmatch(pattern, value), "PREPARE_TOKEN")
    return value


def path(value, *, root=False):
    token(value, r"/[A-Za-z0-9_@./-]{0,1023}")
    require(str(P(value)) == value and not value.startswith("//") and ".." not in P(value).parts
            and (root or value != "/"), "PREPARE_PATH")
    return value


def overlap(a, b):
    return a == b or P(a) in P(b).parents or P(b) in P(a).parents


def encoded(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    require(len(raw) <= LIMIT, "PREPARE_SIZE")
    return raw


def document(raw):
    require(type(raw) is bytes and len(raw) <= LIMIT, "PREPARE_SIZE")
    def unique(pairs):
        result = {}
        for name, value in pairs:
            require(name not in result, "PREPARE_DUPLICATE_KEY"); result[name] = value
        return result
    def rejected(_):
        raise ValueError("PREPARE_NUMBER")
    value = json.loads(raw, object_pairs_hook=unique, parse_float=rejected, parse_constant=rejected)
    pending = [(value, 0)]; count = 0
    while pending:
        item, depth = pending.pop(); count += 1
        require(depth <= 24 and count <= 20000, "PREPARE_COMPLEXITY")
        if type(item) is dict:
            pending.extend((v, depth + 1) for v in item.values())
        elif type(item) is list:
            pending.extend((v, depth + 1) for v in item)
        else:
            require(item is None or type(item) in (str, bool, int), "PREPARE_VALUE")
            if type(item) is int: number(item)
    return value


def decode(raw, digest):
    token(digest, HEX)
    require(hashlib.sha256(raw).hexdigest() == digest, "PREPARE_DIGEST")
    value = document(raw)
    keys(value, ("schema", "purpose", "scope", "baseline", "preparation_id", "host", "mounts", "retained",
                 "retained_domains", "account", "directories", "roots", "parents", "candidate", "tools", "budgets", "settings"))
    require(value["schema"] == SCHEMA and value["scope"] == SCOPE and value["baseline"] == BASELINE
            and value["purpose"] == "ISOLATED_Q2_PREPARATION", "PREPARE_SCOPE")
    token(value["preparation_id"], r"[a-z][a-z0-9]{7,31}")
    host = value["host"]
    keys(host, ("hostname", "boot_id", "initial_userns", "dmi_vendor", "dmi_product"))
    token(host["hostname"], r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}"); token(host["boot_id"], UUID)
    keys(host["initial_userns"], ("device", "inode"))
    number(host["initial_userns"]["device"]); number(host["initial_userns"]["inode"], 1)
    for field in ("dmi_vendor", "dmi_product"): token(host[field], r"[A-Za-z0-9 ().,+_-]{1,128}")
    require(host["dmi_vendor"] in ("QEMU", "KVM") or host["dmi_product"] == "KVM", "PREPARE_ISOLATED_GUEST")
    mounts = value["mounts"]; keys(mounts, ("quota", "system", "journal", "evidence"))
    for mount in mounts.values():
        keys(mount, ("path", "device", "filesystem", "source", "uuid"))
        path(mount["path"], root=True); number(mount["device"], 1); path(mount["source"]); token(mount["uuid"], UUID)
        require(mount["filesystem"] == "ext4", "PREPARE_FILESYSTEM")
    require(len({m["device"] for m in mounts.values()}) == 4, "PREPARE_FILESYSTEM_ALIAS")
    account = value["account"]; keys(account, ("name", "uid", "gid"))
    token(account["name"], r"[a-z][a-z0-9_]{2,30}")
    number(account["uid"], 100, 2**31 - 1); number(account["gid"], 100, 2**31 - 1)
    dirs = value["directories"]; keys(dirs, DIRECTORY_ROLES)
    for role, item in dirs.items():
        keys(item, ("path", "owner", "mode", "filesystem")); path(item["path"])
        require(item["owner"] in ("root", "ordinary") and item["filesystem"] in mounts
                and item["mode"] in (0o700, 0o755), "PREPARE_DIRECTORY")
        require(overlap(mounts[item["filesystem"]]["path"], item["path"]), "PREPARE_DIRECTORY_MOUNT")
        if role in ("state", "authority", "profile_work", "profile_evidence", "profile_temporary", "store_parent"):
            require(item["owner"] == "ordinary" and item["mode"] == 0o700, "PREPARE_ORDINARY_DIRECTORY")
        elif role in ("control", "session", "declarations"):
            require(item["owner"] == "root" and item["mode"] == 0o755, "PREPARE_TRAVERSABLE_DIRECTORY")
        else:
            require(item["owner"] == "root" and item["mode"] == 0o700, "PREPARE_ADMIN_DIRECTORY")
    roots = value["roots"]
    require(type(roots) is list and len(roots) == 7, "PREPARE_ROOT_COUNT")
    expected = {(slot, role) for slot in ("a", "b") for role in ("work", "evidence", "temporary")} | {("store", "retained_store")}
    require({(r.get("slot"), r.get("role")) for r in roots if type(r) is dict} == expected, "PREPARE_ROOT_ROLES")
    for root in roots:
        keys(root, ("ref", "slot", "role", "path", "project_id", "hard_bytes", "inode_hard_limit"))
        token(root["ref"], r"[a-z][a-z0-9_-]{1,63}"); path(root["path"])
        number(root["project_id"], 1, 2**32 - 2); number(root["hard_bytes"], 4096, 64 * 1024**2)
        number(root["inode_hard_limit"], 1, 4096)
        require(root["hard_bytes"] % 4096 == 0, "PREPARE_QUOTA_ALIGNMENT")
        parent = dirs["store_parent" if root["slot"] == "store" else "profile_" + root["role"]]
        require(str(P(root["path"]).parent) == parent["path"] and parent["filesystem"] == "quota", "PREPARE_ROOT_PARENT")
    require(len({r["ref"] for r in roots}) == len({r["path"] for r in roots}) == len({r["project_id"] for r in roots}) == 7,
            "PREPARE_ROOT_ALIAS")
    require(type(value["retained"]) is list and 1 <= len(value["retained"]) <= 64, "PREPARE_RETAINED")
    for item in value["retained"]:
        keys(item, ("path", "device", "inode")); path(item["path"]); number(item["device"], 1); number(item["inode"], 1)
    require(type(value["retained_domains"]) is list and 1 <= len(value["retained_domains"]) <= 128, "PREPARE_RETAINED_DOMAINS")
    for domain in value["retained_domains"]:
        keys(domain, ("project_id", "hard_bytes", "inode_hard_limit"))
        number(domain["project_id"], 1, 2**32-2); number(domain["hard_bytes"], 1); number(domain["inode_hard_limit"], 1)
    old_ids = {d["project_id"] for d in value["retained_domains"]}
    require(len(old_ids) == len(value["retained_domains"]) and not old_ids & {r["project_id"] for r in roots}, "PREPARE_RETAINED_DOMAIN_ALIAS")
    parents = value["parents"]; keys(parents, (*SYSTEM_PARENTS, "ordinary"))
    for role, parent in parents.items():
        keys(parent, ("unit", "memory_bytes", "tasks_max", "cpu_quota_per_sec_usec"))
        token(parent["unit"], r"lhq[a-z0-9]+\.slice")
        number(parent["memory_bytes"], 16*1024**2, 2*1024**3); number(parent["tasks_max"], 2, 128)
        number(parent["cpu_quota_per_sec_usec"], 10000, 1000000)
    require(len({p["unit"] for p in parents.values()}) == 5, "PREPARE_PARENT_ALIAS")
    tools = value["tools"]; keys(tools, TOOLS)
    for tool in tools.values():
        keys(tool, ("path", "sha256")); path(tool["path"]); token(tool["sha256"], HEX)
    candidate = value["candidate"]
    keys(candidate, ("source", "commit", "tree", "wheel", "wheel_sha256", "destination"))
    for field in ("source", "wheel", "destination"): path(candidate[field])
    for field in ("commit", "tree"): token(candidate[field], r"[0-9a-f]{40}")
    token(candidate["wheel_sha256"], HEX)
    paths = [d["path"] for d in dirs.values()] + [candidate["destination"]]
    require(all(not overlap(a, b) for i, a in enumerate(paths) for b in paths[i+1:]), "PREPARE_PATH_ALIAS")
    require(all(not overlap(new, old["path"]) for new in paths for old in value["retained"]), "PREPARE_OLD_PATH_OVERLAP")
    require(all(not overlap(candidate[k], new) for k in ("source", "wheel") for new in paths), "PREPARE_INPUT_OUTPUT_OVERLAP")
    budgets = value["budgets"]
    keys(budgets, (*CEILINGS, "installation_inodes", "state_inodes", "journal_inodes", "capture_inodes",
                  "preparation_seconds", "command_seconds", "command_output_bytes", "retained_scan_bytes", "retained_scan_entries"))
    for name, maximum in CEILINGS.items(): number(budgets[name], 4096, maximum)
    for name in ("installation_inodes", "state_inodes", "journal_inodes", "capture_inodes"): number(budgets[name], 16, 32768)
    number(budgets["preparation_seconds"], 1, 600); number(budgets["command_seconds"], 1, 30)
    number(budgets["command_output_bytes"], 1024, 32768)
    number(budgets["retained_scan_bytes"], 4096, 512*1024**2); number(budgets["retained_scan_entries"], 16, 32768)
    require(type(value["settings"]) is dict, "PREPARE_SETTINGS")
    return value
