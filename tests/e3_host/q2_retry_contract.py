"""Pure contract for the one Owner-authorized CPUQuota startup replacement.

This describes a new attempt. It neither revives the issued old owner nor
proves that its ledger or physical roots are unused; the live attestor must do
that before any reservation or installation effect.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path, PurePosixPath as P

SCHEMA = "local-hand-q2-cpuquota-retry/v1"
SCOPE = "LH-Q2-CPUQUOTA-RETRY-v1"
BASELINE = "d8e49617efecae199b0874f183530794f8c36e6a"
CLOSURE = "b0964e7adb50a49064f522fedbb1d46c3af08911"
CANDIDATE_COMMIT = "9a556322183f0fa80d4edeada4b03c74a26524a5"
CANDIDATE_TREE = "0687d7cd8eaf6a901d565a60b99042827437354c"
CANDIDATE_WHEEL_SHA256 = "0924ac531f3f710cd39838318e8d72b09a4261589df70cf3f650be62a8c8ebcb"
OLD_COMMIT = "d581098252c7e6422d798230359510c2ad9b1d8e"
OLD_TREE = "27a246b92dafc41f9afe0475e2da496865c6797e"
OLD_WHEEL_SHA256 = "ab4e001b73c967f508b7746e1fd6c3639884ea6961d13e6f678b502ce9f5b07d"
HOST_SECONDS = 300
GUEST_SECONDS = 270
PREPARATION_SECONDS = 140
STOP_SECONDS = 3
HOST_CAPTURE_BYTES = 2 * 1024**2
REUSED_DIRECTORIES = ("profile_work", "profile_evidence", "profile_temporary", "store_parent")
CATEGORIES = ("installation", "state", "journal", "capture")
OWNER_FILES = ("reservation.json", "supervisor.stderr", "delivery.json", "capture.json",
               "result.json", "stop.json", "supervisor.stdout", "controls.json")
FRESH_IDENTITIES = ("id", "authority_id", "install_uuid", "operation_id", "epoch",
                    "slot_generation", "session", "ledger_id")


def helper(name):
    spec = importlib.util.spec_from_file_location("_retry_contract_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = helper("q2_prepare_contract")
encoded, document, require = c.encoded, c.document, c.require
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def _contains(parent, child):
    return parent == child or P(parent) in P(child).parents


def _directory(role, item):
    c.keys(item, ("path", "owner", "mode", "filesystem")); c.path(item["path"])
    require(item["filesystem"] in ("system", "journal", "evidence", "quota"), "RETRY_FILESYSTEM_ROLE")
    ordinary = role in ("state", "authority", *REUSED_DIRECTORIES)
    mode = 0o755 if role in ("control", "session", "declarations") else 0o700
    require(item["owner"] == ("ordinary" if ordinary else "root") and item["mode"] == mode
            and type(item["mode"]) is int, "RETRY_DIRECTORY_ACCESS")


def _validate(value):
    c.keys(value, ("schema", "scope", "baseline", "closure", "attempt_id", "original_plan_sha256",
        "original_plan_path", "old_files", "old_prepared", "old_handoff", "old_owner_output", "old_ledger",
        "source", "candidate", "directories", "settings", "retained_inputs", "service"))
    require((value["schema"], value["scope"], value["baseline"], value["closure"]) ==
            (SCHEMA, SCOPE, BASELINE, CLOSURE), "RETRY_AUTHORITY")
    c.token(value["attempt_id"], r"[a-z][a-z0-9]{7,31}")
    c.token(value["service"], r"lhq[a-z0-9-]{1,100}\.service")
    c.token(value["original_plan_sha256"], c.HEX)
    for key in ("original_plan_path", "old_prepared", "old_handoff", "old_owner_output"):
        c.path(value[key])
    old_files = value["old_files"]
    require(type(old_files) is dict and 12 <= len(old_files) <= 4096, "RETRY_OLD_FILES")
    for filename, digest in old_files.items():
        c.path(filename); c.token(digest, c.HEX)
    expected = {value["original_plan_path"], value["old_prepared"], value["old_handoff"],
                str(P(value["old_prepared"]).parent / "recovery-result.json")}
    expected.update(str(P(value["old_owner_output"]) / name) for name in OWNER_FILES)
    require(expected <= old_files.keys(), "RETRY_MISSING_OLD_EVIDENCE")
    require(old_files[value["original_plan_path"]] == value["original_plan_sha256"], "RETRY_ORIGINAL_PLAN_PIN")
    require(P(value["old_prepared"]).name == "prepared.json"
            and P(value["old_handoff"]).name == "handoff.json"
            and P(value["old_prepared"]).parent == P(value["old_handoff"]).parent, "RETRY_OLD_RECORD_LOCATIONS")
    ledger = value["old_ledger"]
    c.keys(ledger, ("path", "device", "inode", "mode", "uid", "ledger_id", "generation"))
    c.path(ledger["path"]); c.number(ledger["device"], 1); c.number(ledger["inode"], 1)
    c.number(ledger["uid"], 100, 2**31-1)
    require(type(ledger["mode"]) is int and ledger["mode"] == 0o600, "RETRY_OLD_LEDGER_MODE")
    c.token(ledger["ledger_id"], r"[a-z0-9][a-z0-9._-]{0,127}")
    require(type(ledger["generation"]) is list and len(ledger["generation"]) == 2
            and all(type(n) is int and n == 1 for n in ledger["generation"]), "RETRY_OLD_LEDGER_GENERATION")
    source = value["source"]
    c.keys(source, ("commit", "tree", "files"))
    for key in ("commit", "tree"): c.token(source[key], r"[0-9a-f]{40}")
    require(source["commit"] not in (BASELINE, CLOSURE, CANDIDATE_COMMIT, OLD_COMMIT), "RETRY_SOURCE_NOT_IMPLEMENTATION")
    require(type(source["files"]) is dict and 4 <= len(source["files"]) <= 128, "RETRY_SOURCE_FILES")
    for filename, digest in source["files"].items():
        c.path(filename); c.token(digest, c.HEX)
        require(P(filename).suffix == ".py", "RETRY_SOURCE_FILE_TYPE")
    require(len({str(P(filename).parent) for filename in source["files"]}) == 1
            and {"q2_retry.py", "q2_retry_contract.py", "q2_retry_driver.py", "q2_retry_delivery.py"}
            <= {P(filename).name for filename in source["files"]}, "RETRY_SOURCE_LAYOUT")
    candidate = value["candidate"]
    c.keys(candidate, ("source", "commit", "tree", "wheel", "wheel_sha256", "destination"))
    for key in ("source", "wheel", "destination"): c.path(candidate[key])
    require((candidate["commit"], candidate["tree"], candidate["wheel_sha256"]) ==
            (CANDIDATE_COMMIT, CANDIDATE_TREE, CANDIDATE_WHEEL_SHA256), "RETRY_FIXED_CANDIDATE")
    dirs = value["directories"]; c.keys(dirs, c.DIRECTORY_ROLES)
    for role, item in dirs.items(): _directory(role, item)
    paths = [item["path"] for item in dirs.values()] + [candidate["destination"]]
    require(all(not c.overlap(a, b) for i, a in enumerate(paths) for b in paths[i+1:]), "RETRY_NEW_PATH_ALIAS")
    inputs = [candidate["source"], candidate["wheel"], *source["files"]]
    require(not c.overlap(candidate["source"], candidate["wheel"]), "RETRY_CANDIDATE_INPUT_ALIAS")
    require(all(not c.overlap(stage, candidate["source"]) and not c.overlap(stage, candidate["wheel"])
                for stage in source["files"]), "RETRY_RUNTIME_TOOL_ALIAS")
    require(all(not c.overlap(input_path, output) for input_path in inputs for output in paths), "RETRY_INPUT_OUTPUT_ALIAS")
    retained = value["retained_inputs"]
    require(type(retained) is list and 4 <= len(retained) <= 128, "RETRY_RETAINED_INPUTS")
    for item in retained:
        c.keys(item, ("path", "category")); c.path(item["path"])
        require(item["category"] in CATEGORIES, "RETRY_RETAINED_CATEGORY")
    require(all(not c.overlap(a["path"], b["path"]) for i, a in enumerate(retained) for b in retained[i+1:]),
            "RETRY_RETAINED_ALIAS")
    new_paths = [dirs[role]["path"] for role in c.DIRECTORY_ROLES if role not in REUSED_DIRECTORIES]
    new_paths.append(candidate["destination"])
    old_paths = [*old_files, ledger["path"], value["old_owner_output"], *(item["path"] for item in retained)]
    require(all(not c.overlap(new, old) for new in new_paths for old in old_paths), "RETRY_OLD_PATH_ALIAS")
    helper("q2_prepare_driver").validate_settings(value["settings"])
    settings = value["settings"]
    require(settings["identity"]["generation"] == 1, "RETRY_NEW_LEDGER_GENERATION")
    cap = settings["capacity_management"]
    require(cap["cpu_ns"] <= 400*10**9 and cap["memory_bytes"] <= 1536*1024**2 and cap["pids"] <= 1024,
            "RETRY_RUNTIME_CAPACITY")
    require(value["service"] not in {control["unit"] for control in settings["controllers"].values()}, "RETRY_SERVICE_ALIAS")
    return value


def decode(raw, digest):
    c.token(digest, c.HEX)
    require(type(raw) is bytes and sha(raw) == digest, "RETRY_PLAN_DIGEST")
    return _validate(document(raw))


def bind(original_plan, retry):
    """Derive an explicit new plan while preserving original resource limits.

    The old object is independently decoded. No old schema/scope is used to
    misrepresent the derived plan as another original preparation.
    """
    retry = _validate(copy.deepcopy(retry))
    original = c.decode(encoded(original_plan), retry["original_plan_sha256"])
    helper("q2_prepare_driver").validate_plan(original)
    old_candidate = original["candidate"]
    require((old_candidate["commit"], old_candidate["tree"], old_candidate["wheel_sha256"]) ==
            (OLD_COMMIT, OLD_TREE, OLD_WHEEL_SHA256), "RETRY_OLD_CANDIDATE")
    old_attempts = {original["preparation_id"], P(retry["old_prepared"]).parent.name,
                    original["settings"]["identity"]["id"]}
    require(retry["attempt_id"] not in old_attempts, "RETRY_ATTEMPT_REUSE")
    require(all(root["hard_bytes"] == 1024**2 and root["inode_hard_limit"] == 128 for root in original["roots"]),
            "RETRY_ROOT_LIMIT_CHANGED")
    require(len(original["retained_domains"]) == 4 and sum(d["hard_bytes"] for d in original["retained_domains"]) == 196*1024**2,
            "RETRY_Q1_COMMITMENT")
    ledger = retry["old_ledger"]
    require(ledger["path"] == str(P(original["directories"]["state"]["path"]) / "jobs.sqlite")
            and ledger["uid"] == original["account"]["uid"]
            and ledger["ledger_id"] == original["settings"]["identity"]["ledger_id"], "RETRY_OLD_LEDGER_BINDING")
    policy_path = str(P(original["directories"]["authority"]["path"]) / "policy.json")
    require(policy_path in retry["old_files"], "RETRY_OLD_POLICY_PIN")
    require(retry["old_owner_output"] == str(P(original["directories"]["capture"]["path"]) / "owner_output"),
            "RETRY_OLD_OWNER_LOCATION")
    for role, directory in retry["directories"].items():
        previous = original["directories"][role]
        require({k: directory[k] for k in ("owner", "mode", "filesystem")} ==
                {k: previous[k] for k in ("owner", "mode", "filesystem")}, "RETRY_DIRECTORY_ROLE_CHANGED")
        require(_contains(original["mounts"][directory["filesystem"]]["path"], directory["path"]), "RETRY_DIRECTORY_MOUNT")
        if role in REUSED_DIRECTORIES:
            require(directory == previous, "RETRY_QUOTA_PARENT_CHANGED")
    new_paths = [retry["directories"][role]["path"] for role in c.DIRECTORY_ROLES if role not in REUSED_DIRECTORIES]
    new_paths.append(retry["candidate"]["destination"])
    old_paths = [d["path"] for d in original["directories"].values()]
    old_paths += [old_candidate[key] for key in ("source", "wheel", "destination")]
    old_paths += [item["path"] for item in original["retained"]]
    old_paths += [*retry["old_files"], ledger["path"], retry["old_owner_output"]]
    require(all(not c.overlap(new, old) for new in new_paths for old in old_paths), "RETRY_ORIGINAL_PATH_ALIAS")
    require(all(not c.overlap(new, old) for new in [retry["candidate"]["source"], retry["candidate"]["wheel"], *retry["source"]["files"]]
                for old in old_paths), "RETRY_STAGING_OLD_ALIAS")
    new_inputs = [retry["candidate"]["source"], retry["candidate"]["wheel"], *retry["source"]["files"]]
    for item in retry["retained_inputs"]:
        if item["category"] == "installation" and any(_contains(item["path"], name) for name in new_inputs):
            require(not any(c.overlap(item["path"], old) for old in old_paths), "RETRY_MIXED_OLD_NEW_STAGING")
    def covered(path, category):
        return any(item["category"] == category and _contains(item["path"], path) for item in retry["retained_inputs"])
    required_accounting = [(old_candidate[key], "installation") for key in ("source", "wheel", "destination")]
    for role, directory in original["directories"].items():
        if role not in REUSED_DIRECTORIES:
            category = "journal" if role == "journal" else "capture" if role in ("capture", "declarations") else "state"
            required_accounting.append((directory["path"], category))
    required_accounting += [(retry["candidate"][key], "installation") for key in ("source", "wheel")]
    required_accounting += [(filename, "installation") for filename in retry["source"]["files"]]
    require(all(covered(path, category) for path, category in required_accounting), "RETRY_ACCOUNTING_COVERAGE")
    new_settings, old_settings = retry["settings"], original["settings"]
    for key in ("original_budgets", "limits", "management", "capacity_management", "owner"):
        require(new_settings[key] == old_settings[key], "RETRY_SETTINGS_LIMIT_CHANGED")
    for role, control in new_settings["controllers"].items():
        previous = old_settings["controllers"][role]
        require({k: v for k, v in control.items() if k != "unit"} ==
                {k: v for k, v in previous.items() if k != "unit"}, "RETRY_CONTROLLER_LIMIT_CHANGED")
    old_units = {p["unit"] for p in original["parents"].values()} | {v["unit"] for v in old_settings["controllers"].values()}
    old_units.update("lhq" + attempt + ".service" for attempt in old_attempts)
    new_units = {retry["service"], *(v["unit"] for v in new_settings["controllers"].values())}
    require(len(new_units) == 3 and not old_units & new_units, "RETRY_UNIT_REUSE")
    old_identity, new_identity = old_settings["identity"], new_settings["identity"]
    require(all(new_identity[key] != old_identity[key] for key in FRESH_IDENTITIES), "RETRY_IDENTITY_REUSE")
    require(new_identity["deployment_epoch"] > old_identity["deployment_epoch"], "RETRY_DEPLOYMENT_EPOCH_REUSE")
    result = copy.deepcopy(original)
    result.update(schema=SCHEMA, purpose="ISOLATED_Q2_CPUQUOTA_RETRY", scope=SCOPE, baseline=BASELINE,
                  preparation_id=retry["attempt_id"], candidate=retry["candidate"], directories=retry["directories"], settings=new_settings)
    result["budgets"]["preparation_seconds"] = PREPARATION_SECONDS
    helper("q2_prepare_driver").validate_plan(result)
    return result
