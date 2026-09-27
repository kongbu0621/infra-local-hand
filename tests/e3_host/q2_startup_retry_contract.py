"""Pure, exact contract for the one approved supervisor-startup replacement.

Both consumed predecessors retain their original schemas and bytes. Decoding
does no host I/O; live attestation must still establish the declared identities,
unused ledgers/roots and preservation before any new persistent effect.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path, PurePosixPath as P

SCHEMA = "local-hand-q2-supervisor-startup-retry/v1"
SCOPE = "LH-Q2-SUPERVISOR-STARTUP-RETRY-v1"
RULE = "10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
BASELINE = "47b351b2b943bf1d6f1c71cfeb031157a2eb70cc"
CLOSURE = "d4a925c883672fadc7d1b10a8dfe58df18b922cd"
OWNER_DECISION = "LH-Q2-SUPERVISOR-STARTUP-RETRY-CLOSURE-20260927-01"
CANDIDATE_COMMIT = "b49d3df3d1e76813faf08e59ab4975e25279c2fc"
CANDIDATE_TREE = "2d957ccf1d9cbdf5e538189c6b68d56f34590a42"
CANDIDATE_WHEEL_SHA256 = "c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b"
PREVIOUS_SOURCE_COMMIT = "15af5f19b27211f237f1d66f7e11c9aeef59a3a5"
PREVIOUS_SOURCE_TREE = "a300cd9888960bf9d25eef61cc4098242e1a7f70"
HOST_SECONDS = 300
GUEST_SECONDS = 270
PREPARATION_SECONDS = 140
STOP_SECONDS = 3
HOST_CAPTURE_BYTES = 2 * 1024**2
PREDECESSOR_KINDS = ("CPUQUOTA_PARSE_BEFORE_CHILD", "SUPERVISOR_STARTED_PERMISSION_FAILURE")
REUSED_DIRECTORIES = ("profile_work", "profile_evidence", "profile_temporary", "store_parent")
CATEGORIES = ("installation", "state", "journal", "capture")
FRESH_IDENTITIES = ("id", "authority_id", "install_uuid", "operation_id", "epoch",
                    "slot_generation", "session", "ledger_id")
OWNER_FILES = ("reservation.json", "supervisor.stderr", "delivery.json", "capture.json",
               "result.json", "stop.json", "supervisor.stdout", "controls.json")
REQUIRED_SOURCE_FILES = frozenset({
    "q2_startup_retry_contract.py", "q2_startup_retry.py", "q2_startup_retry_driver.py",
    "q2_startup_retry_delivery.py", "q2_startup_retry_collect.py", "q2_startup_retry_entry.py",
    "q2_startup_retry_bootstrap.py", "q2_retry_contract.py", "q2_retry.py",
    "q2_retry_collect.py", "q2_retry_delivery.py", "q2_retry_bundle.py",
    "q2_prepare.py", "q2_prepare_contract.py", "q2_prepare_build.py", "q2_prepare_driver.py",
    "q2_prepare_assembly.py", "q2_prepare_delivery.py", "q2_prepare_run.py",
})
STARTUP_RECORDS = ("retry-intent.json", "retry-preparation.json", "delivery-envelope.json",
    "new-request-issuance.json", "new-request.json", "authority.json", "manifest.json")
RESERVATION_KINDS = {
    "OWNER_COMMITMENT": (2, "capture"), "BOOTSTRAP_COMMITMENT": (2, "installation"),
    "PREPARATION_CEILING": (1, "state"), "PREPARATION_SNAPSHOT": (1, "state"),
    "RECOVERY_SNAPSHOT": (1, "state"), "RETRY_SNAPSHOT": (1, "state"),
    "RECOVERY_STAGE": (1, "installation"), "BOOTSTRAP_ATTESTATION": (1, "installation"),
}


def helper(name):
    spec = importlib.util.spec_from_file_location("_startup_contract_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = helper("q2_prepare_contract")
legacy = helper("q2_retry_contract")
encoded, document, require = c.encoded, c.document, c.require


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def contains(parent, child):
    return parent == child or P(parent) in P(child).parents


def _ledger(pin):
    c.keys(pin, ("path", "device", "inode", "mode", "uid", "ledger_id", "generation"))
    c.path(pin["path"])
    for key in ("device", "inode"): c.number(pin[key], 1)
    c.number(pin["uid"], 100, 2**31 - 1)
    require(type(pin["mode"]) is int and pin["mode"] == 0o600, "STARTUP_RETRY_LEDGER_MODE")
    c.token(pin["ledger_id"], r"[a-z0-9][a-z0-9._-]{0,127}")
    require(type(pin["generation"]) is list and len(pin["generation"]) == 2
        and all(type(n) is int and n == 1 for n in pin["generation"]), "STARTUP_RETRY_LEDGER_GENERATION")


def _predecessors(value):
    items = value["predecessors"]
    require(type(items) is list and len(items) == 2, "STARTUP_RETRY_PREDECESSORS")
    for index, item in enumerate(items):
        c.keys(item, ("kind", "plan_path", "plan_sha256", "prepared_path", "handoff_path",
            "owner_output", "ledger", "policy_path", "failed_units"))
        require(item["kind"] == PREDECESSOR_KINDS[index], "STARTUP_RETRY_PREDECESSOR_KIND")
        for key in ("plan_path", "prepared_path", "handoff_path", "owner_output", "policy_path"):
            c.path(item[key])
        c.token(item["plan_sha256"], c.HEX)
        require(P(item["prepared_path"]).name == "prepared.json"
            and P(item["handoff_path"]).name == "handoff.json"
            and P(item["prepared_path"]).parent == P(item["handoff_path"]).parent,
            "STARTUP_RETRY_PREDECESSOR_RECORD_LOCATION")
        _ledger(item["ledger"])
        expected = {item[key] for key in ("plan_path", "prepared_path", "handoff_path", "policy_path")}
        expected.add(item["ledger"]["path"])
        expected.update(str(P(item["owner_output"]) / name) for name in OWNER_FILES)
        expected.update(str(P(item["prepared_path"]).parent / name)
            for name in ("authority.json", "manifest.json"))
        if index == 0:
            expected.update(str(P(item["prepared_path"]).parent / name)
                for name in ("recovery-result.json", "first-request-issuance.json", "first-request.json"))
        else:
            expected.update(str(P(item["prepared_path"]).parent / name) for name in STARTUP_RECORDS)
        require(expected <= value["old_files"].keys(), "STARTUP_RETRY_MISSING_HISTORY")
        require(value["old_files"][item["plan_path"]] == item["plan_sha256"], "STARTUP_RETRY_HISTORY_PLAN_PIN")
        units = item["failed_units"]
        require(type(units) is list and len(units) == 2, "STARTUP_RETRY_FAILED_UNITS")
        roles = ("preparation", "recovery") if index == 0 else ("service", "supervisor")
        for role, unit in zip(roles, units):
            c.keys(unit, ("role", "unit", "invocation_id", "exec_main_code", "exec_main_status"))
            require(unit["role"] == role, "STARTUP_RETRY_FAILED_ROLE")
            c.token(unit["unit"], r"lhq[a-z0-9-]{1,100}\.service")
            c.token(unit["invocation_id"], r"[0-9a-f]{32}")
            require(unit["invocation_id"] != "0" * 32
                and type(unit["exec_main_code"]) is int and unit["exec_main_code"] == 1
                and type(unit["exec_main_status"]) is int and unit["exec_main_status"] == 3,
                "STARTUP_RETRY_FAILED_IDENTITY")
    require(items[0]["plan_path"] == value["original_plan_path"]
        and items[0]["plan_sha256"] == value["original_plan_sha256"], "STARTUP_RETRY_ORIGINAL_BINDING")
    require(len({(x["ledger"]["device"], x["ledger"]["inode"]) for x in items}) == 2
        and len({x["ledger"]["path"] for x in items}) == 2
        and len({x["ledger"]["ledger_id"] for x in items}) == 2, "STARTUP_RETRY_LEDGER_ALIAS")
    require(len({u["invocation_id"] for item in items for u in item["failed_units"]}) == 4,
        "STARTUP_RETRY_FAILED_INVOCATION_ALIAS")


def _reservations(value):
    rows = value["reservations"]
    require(type(rows) is list and len(rows) == sum(count for count, _ in RESERVATION_KINDS.values()),
        "STARTUP_RETRY_RESERVATIONS")
    for row in rows:
        c.keys(row, ("kind", "path", "category", "covered_paths"))
        require(row["kind"] in RESERVATION_KINDS, "STARTUP_RETRY_RESERVATION_KIND")
        require(row["category"] == RESERVATION_KINDS[row["kind"]][1], "STARTUP_RETRY_RESERVATION_CATEGORY")
        c.path(row["path"])
        require(row["path"] in value["old_files"], "STARTUP_RETRY_RESERVATION_PIN")
        paths = row["covered_paths"]
        require(type(paths) is list and len(paths) == (2 if row["kind"] in
            ("OWNER_COMMITMENT", "BOOTSTRAP_COMMITMENT") else 1 if row["kind"] == "RECOVERY_STAGE" else 0),
            "STARTUP_RETRY_RESERVATION_COVERAGE")
        for path in paths: c.path(path)
        require(all(not c.overlap(a, b) for i, a in enumerate(paths) for b in paths[i + 1:]),
            "STARTUP_RETRY_RESERVATION_ALIAS")
    require(len({row["path"] for row in rows}) == len(rows), "STARTUP_RETRY_RESERVATION_DUPLICATE")
    require(all(sum(row["kind"] == kind for row in rows) == count
        for kind, (count, _) in RESERVATION_KINDS.items()), "STARTUP_RETRY_RESERVATION_KIND_COUNT")


def _validate(value):
    c.keys(value, ("schema", "scope", "rule", "baseline", "closure", "owner_decision", "attempt_id",
        "original_plan_path", "original_plan_sha256", "old_files", "predecessors", "reservations",
        "source", "candidate", "directories", "settings", "retained_inputs", "service"))
    require(tuple(value[key] for key in ("schema", "scope", "rule", "baseline", "closure", "owner_decision"))
        == (SCHEMA, SCOPE, RULE, BASELINE, CLOSURE, OWNER_DECISION), "STARTUP_RETRY_AUTHORITY")
    c.token(value["attempt_id"], r"[a-z][a-z0-9]{7,31}")
    c.token(value["service"], r"lhq[a-z0-9-]{1,100}\.service")
    c.path(value["original_plan_path"]); c.token(value["original_plan_sha256"], c.HEX)
    old_files = value["old_files"]
    require(type(old_files) is dict and 24 <= len(old_files) <= 4096, "STARTUP_RETRY_OLD_FILES")
    for path, digest in old_files.items(): c.path(path); c.token(digest, c.HEX)
    _predecessors(value)
    _reservations(value)
    source = value["source"]
    c.keys(source, ("commit", "tree", "files"))
    for key in ("commit", "tree"): c.token(source[key], r"[0-9a-f]{40}")
    require(source["commit"] not in (RULE, BASELINE, CLOSURE, CANDIDATE_COMMIT,
        legacy.CANDIDATE_COMMIT, legacy.OLD_COMMIT), "STARTUP_RETRY_SOURCE_NOT_IMPLEMENTATION")
    files = source["files"]
    require(type(files) is dict and len(REQUIRED_SOURCE_FILES) <= len(files) <= 64,
        "STARTUP_RETRY_SOURCE_FILES")
    for path, digest in files.items():
        c.path(path); c.token(digest, c.HEX)
        c.token(P(path).name, r"q2_[a-z0-9_]+\.py")
    require(len({str(P(path).parent) for path in files}) == 1
        and REQUIRED_SOURCE_FILES <= {P(path).name for path in files}, "STARTUP_RETRY_SOURCE_CLOSURE")
    candidate = value["candidate"]
    c.keys(candidate, ("source", "commit", "tree", "wheel", "wheel_sha256", "destination"))
    for key in ("source", "wheel", "destination"): c.path(candidate[key])
    require(tuple(candidate[key] for key in ("commit", "tree", "wheel_sha256")) ==
        (CANDIDATE_COMMIT, CANDIDATE_TREE, CANDIDATE_WHEEL_SHA256), "STARTUP_RETRY_FIXED_CANDIDATE")
    directories = value["directories"]; c.keys(directories, c.DIRECTORY_ROLES)
    for role, item in directories.items(): legacy._directory(role, item)
    outputs = [item["path"] for item in directories.values()] + [candidate["destination"]]
    require(all(not c.overlap(a, b) for i, a in enumerate(outputs) for b in outputs[i + 1:]),
        "STARTUP_RETRY_NEW_PATH_ALIAS")
    inputs = [candidate["source"], candidate["wheel"], *files]
    require(not c.overlap(candidate["source"], candidate["wheel"])
        and all(not c.overlap(path, candidate[k]) for path in files for k in ("source", "wheel")),
        "STARTUP_RETRY_RUNTIME_TOOL_ALIAS")
    require(all(not c.overlap(path, output) for path in inputs for output in outputs),
        "STARTUP_RETRY_INPUT_OUTPUT_ALIAS")
    retained = value["retained_inputs"]
    require(type(retained) is list and 8 <= len(retained) <= 128, "STARTUP_RETRY_RETAINED_INPUTS")
    for item in retained:
        c.keys(item, ("path", "category")); c.path(item["path"])
        require(item["category"] in CATEGORIES, "STARTUP_RETRY_RETAINED_CATEGORY")
    require(all(not c.overlap(a["path"], b["path"]) for i, a in enumerate(retained) for b in retained[i + 1:]),
        "STARTUP_RETRY_RETAINED_ALIAS")
    fresh_paths = [directories[k]["path"] for k in c.DIRECTORY_ROLES if k not in REUSED_DIRECTORIES]
    fresh_paths.append(candidate["destination"])
    require(all(not c.overlap(new, old) for new in fresh_paths
        for old in [*old_files, *(x["path"] for x in retained)]), "STARTUP_RETRY_OLD_PATH_ALIAS")
    helper("q2_prepare_driver").validate_settings(value["settings"])
    settings = value["settings"]
    require(settings["identity"]["generation"] == 1, "STARTUP_RETRY_NEW_LEDGER_GENERATION")
    cap = settings["capacity_management"]
    require(cap["cpu_ns"] <= 400 * 10**9 and cap["memory_bytes"] <= 1536 * 1024**2
        and cap["pids"] <= 1024, "STARTUP_RETRY_RUNTIME_CAPACITY")
    return value


def decode(raw, digest):
    c.token(digest, c.HEX)
    require(type(raw) is bytes and sha(raw) == digest, "STARTUP_RETRY_PLAN_DIGEST")
    return _validate(document(raw))


def _category(role):
    return "journal" if role == "journal" else "capture" if role in ("capture", "declarations") else "state"


def bind(original_plan, retry, previous_retry_plan):
    """Purely bind two independently decoded predecessors to one new plan."""
    retry = _validate(copy.deepcopy(retry))
    original = c.decode(encoded(original_plan), retry["original_plan_sha256"])
    previous = legacy.decode(encoded(previous_retry_plan), retry["predecessors"][1]["plan_sha256"])
    historical = legacy.bind(original, previous)
    require((previous["source"]["commit"], previous["source"]["tree"]) ==
        (PREVIOUS_SOURCE_COMMIT, PREVIOUS_SOURCE_TREE), "STARTUP_RETRY_PREVIOUS_SOURCE")
    require(retry["source"]["commit"] != previous["source"]["commit"]
        and retry["source"]["tree"] != previous["source"]["tree"], "STARTUP_RETRY_ORCHESTRATION_REUSE")
    require(previous["original_plan_path"] == retry["original_plan_path"]
        and previous["original_plan_sha256"] == retry["original_plan_sha256"], "STARTUP_RETRY_HISTORY_CHAIN")
    require(all(retry["old_files"].get(path) == digest for path, digest in previous["old_files"].items()),
        "STARTUP_RETRY_HISTORY_PIN_CHANGED")
    first, second = retry["predecessors"]
    require(first["prepared_path"] == previous["old_prepared"]
        and first["handoff_path"] == previous["old_handoff"]
        and first["owner_output"] == previous["old_owner_output"]
        and first["ledger"] == previous["old_ledger"], "STARTUP_RETRY_FIRST_PREDECESSOR")
    require([x["unit"] for x in first["failed_units"]] == ["lhq" + original["preparation_id"] + ".service",
        "lhq" + P(first["prepared_path"]).parent.name + ".service"], "STARTUP_RETRY_ORIGINAL_FAILED_UNIT_BINDING")
    for item, old in zip((first, second), (original, historical)):
        require(item["ledger"]["path"] == str(P(old["directories"]["state"]["path"]) / "jobs.sqlite")
            and item["ledger"]["uid"] == original["account"]["uid"]
            and item["ledger"]["ledger_id"] == old["settings"]["identity"]["ledger_id"],
            "STARTUP_RETRY_LEDGER_BINDING")
        require(item["policy_path"] == str(P(old["directories"]["authority"]["path"]) / "policy.json")
            and item["owner_output"] == str(P(old["directories"]["capture"]["path"]) / "owner_output"),
            "STARTUP_RETRY_HISTORY_LOCATION")
    require(second["prepared_path"] == str(P(previous["directories"]["reservation"]["path"]) / "prepared.json")
        and second["handoff_path"] == str(P(previous["directories"]["reservation"]["path"]) / "handoff.json"),
        "STARTUP_RETRY_SECOND_PREDECESSOR")
    require([x["unit"] for x in second["failed_units"]] ==
        [previous["service"], previous["settings"]["controllers"]["supervisor"]["unit"]],
        "STARTUP_RETRY_FAILED_UNIT_BINDING")
    _bind_paths(original, historical, previous, retry)
    _bind_reservations(original, historical, retry)
    _bind_identities(original, historical, previous, retry)
    result = copy.deepcopy(original)
    result.update(schema=SCHEMA, purpose="ISOLATED_Q2_SUPERVISOR_STARTUP_RETRY", scope=SCOPE,
        baseline=BASELINE, preparation_id=retry["attempt_id"], candidate=retry["candidate"],
        directories=retry["directories"], settings=retry["settings"])
    result["budgets"]["preparation_seconds"] = PREPARATION_SECONDS
    helper("q2_prepare_driver").validate_plan(result)
    return result


def _bind_paths(original, historical, previous, retry):
    require(contains(original["mounts"]["system"]["path"], retry["candidate"]["destination"]),
        "STARTUP_RETRY_INSTALLATION_MOUNT")
    for role, directory in retry["directories"].items():
        before = original["directories"][role]
        require({k: directory[k] for k in ("owner", "mode", "filesystem")} ==
            {k: before[k] for k in ("owner", "mode", "filesystem")}, "STARTUP_RETRY_DIRECTORY_ROLE_CHANGED")
        require(contains(original["mounts"][directory["filesystem"]]["path"], directory["path"]),
            "STARTUP_RETRY_DIRECTORY_MOUNT")
        if role in REUSED_DIRECTORIES:
            require(directory == before == historical["directories"][role], "STARTUP_RETRY_QUOTA_PARENT_CHANGED")
    old_paths = set(retry["old_files"])
    required = []
    for old in (original, historical):
        old_paths.update(x["path"] for x in old["directories"].values())
        old_paths.update(old["candidate"][key] for key in ("source", "wheel", "destination"))
        old_paths.update(x["path"] for x in old["retained"])
        required.extend((old["candidate"][key], "installation") for key in ("source", "wheel", "destination"))
        required.extend((x["path"], _category(role)) for role, x in old["directories"].items()
            if role not in REUSED_DIRECTORIES)
        require(str(P(old["directories"]["declarations"]["path"]) / "owner_declarations" / "envelope.json")
            in retry["old_files"], "STARTUP_RETRY_ISSUED_ENVELOPE_PIN")
    old_paths.update(previous["source"]["files"])
    old_paths.update(x["path"] for x in previous["retained_inputs"])
    required.extend((x["path"], x["category"]) for x in previous["retained_inputs"])
    fresh = [retry["directories"][role]["path"] for role in c.DIRECTORY_ROLES if role not in REUSED_DIRECTORIES]
    fresh.extend(retry["candidate"][key] for key in ("source", "wheel", "destination"))
    fresh.extend(retry["source"]["files"])
    require(all(not c.overlap(new, old) for new in fresh for old in old_paths), "STARTUP_RETRY_HISTORICAL_PATH_ALIAS")
    inputs = [retry["candidate"][key] for key in ("source", "wheel")] + list(retry["source"]["files"])
    for item in retry["retained_inputs"]:
        if any(contains(item["path"], name) for name in inputs):
            require(item["category"] == "installation" and not any(c.overlap(item["path"], old) for old in old_paths),
                "STARTUP_RETRY_MIXED_OLD_NEW_STAGING")
    required.extend((path, "installation") for path in inputs)
    required.extend((item["plan_path"], "installation") for item in retry["predecessors"])
    def covered(path, category=None):
        return any((category is None or row["category"] == category) and contains(row["path"], path)
            for row in retry["retained_inputs"])
    require(all(covered(path, category) for path, category in required)
        and all(covered(path) for path in retry["old_files"]), "STARTUP_RETRY_ACCOUNTING_COVERAGE")


def required_reservations(original, historical, retry, *, recovery_stage):
    """Derive fixed history records, not financial assertions from filenames.

    The live attestor additionally binds recovery_stage to the recovery
    intent's protected orchestration source and checks each record's schema.
    Ceilings/snapshots are retained evidence, not another independent ceiling.
    """
    c.path(recovery_stage)
    require(P(recovery_stage).name == "stage.json", "STARTUP_RETRY_RECOVERY_STAGE")
    rows = []
    def add(kind, path, paths=()):
        rows.append(dict(kind=kind, path=str(path), category=RESERVATION_KINDS[kind][1], covered_paths=list(paths)))
    first, second = retry["predecessors"]
    for item, old in zip((first, second), (original, historical)):
        add("OWNER_COMMITMENT", P(item["owner_output"]) / "reservation.json",
            [old["directories"][key]["path"] for key in ("capture", "declarations")])
        stage = str(P(old["candidate"]["source"]).parent)
        require(contains(stage, old["candidate"]["wheel"]), "STARTUP_RETRY_BOOTSTRAP_LAYOUT")
        add("BOOTSTRAP_COMMITMENT", stage + ".intent.json", [stage, old["candidate"]["destination"]])
    add("PREPARATION_CEILING", P(original["directories"]["reservation"]["path"]) / "intent.json")
    add("PREPARATION_SNAPSHOT", P(original["directories"]["reservation"]["path"]) / "preflight.json")
    add("RECOVERY_SNAPSHOT", P(first["prepared_path"]).parent / "recovery-intent.json")
    add("RETRY_SNAPSHOT", P(second["prepared_path"]).parent / "retry-intent.json")
    add("RECOVERY_STAGE", recovery_stage, [original["candidate"]["destination"]])
    add("BOOTSTRAP_ATTESTATION", P(historical["candidate"]["source"]).parent / "bootstrap-attestation.json")
    return rows


def _bind_reservations(original, historical, retry):
    stage = next(row["path"] for row in retry["reservations"] if row["kind"] == "RECOVERY_STAGE")
    expected = required_reservations(original, historical, retry, recovery_stage=stage)
    require(sorted(retry["reservations"], key=lambda row: row["path"]) == sorted(expected, key=lambda row: row["path"]),
        "STARTUP_RETRY_RESERVATION_BINDING")
    for row in retry["reservations"]:
        require(any(item["category"] == row["category"] and contains(item["path"], row["path"])
            for item in retry["retained_inputs"]), "STARTUP_RETRY_RESERVATION_ACCOUNTING")
    original_intent = str(P(original["directories"]["reservation"]["path"]) / "intent.json")
    require(retry["old_files"][original_intent] == retry["original_plan_sha256"], "STARTUP_RETRY_ORIGINAL_INTENT")


def _bind_identities(original, historical, previous, retry):
    new = retry["settings"]
    for old in (original, historical):
        settings = old["settings"]
        require(all(new["identity"][key] == settings["identity"][key]
            for key in ("node_id", "profile_ref", "principal_id")), "STARTUP_RETRY_STABLE_IDENTITY_CHANGED")
        for key in ("original_budgets", "limits", "management", "capacity_management", "owner"):
            require(new[key] == settings[key], "STARTUP_RETRY_SETTINGS_LIMIT_CHANGED")
        for role, control in new["controllers"].items():
            require({k: v for k, v in control.items() if k != "unit"} ==
                {k: v for k, v in settings["controllers"][role].items() if k != "unit"},
                "STARTUP_RETRY_CONTROLLER_LIMIT_CHANGED")
    old_ids = {old["settings"]["identity"][key] for old in (original, historical) for key in FRESH_IDENTITIES}
    old_ids.update(request_id for old in (original, historical)
        for request_id in derived_request_ids(old["settings"]["identity"]["id"]))
    old_ids.update(unit["invocation_id"] for predecessor in retry["predecessors"] for unit in predecessor["failed_units"])
    old_attempts = {original["preparation_id"], previous["attempt_id"],
        *(P(row["prepared_path"]).parent.name for row in retry["predecessors"])}
    require(retry["attempt_id"] not in old_attempts | old_ids, "STARTUP_RETRY_ATTEMPT_REUSE")
    fresh_ids = [new["identity"][key] for key in FRESH_IDENTITIES]
    require(len(set(fresh_ids)) == len(fresh_ids) and not set(fresh_ids) & (old_ids | old_attempts),
        "STARTUP_RETRY_IDENTITY_REUSE")
    requests = derived_request_ids(new["identity"]["id"])
    require(len(set(requests)) == 6 and not set(requests) & (old_ids | old_attempts | set(fresh_ids)),
        "STARTUP_RETRY_REQUEST_ID_REUSE")
    require(new["identity"]["deployment_epoch"] > max(old["settings"]["identity"]["deployment_epoch"]
        for old in (original, historical)), "STARTUP_RETRY_DEPLOYMENT_EPOCH_REUSE")
    units = {row["unit"] for old in (original, historical) for row in old["settings"]["controllers"].values()}
    units.update(row["unit"] for row in original["parents"].values())
    units.add(previous["service"])
    units.update("lhq" + str(token) + ".service" for token in old_attempts | old_ids)
    fresh_units = {retry["service"], *(x["unit"] for x in new["controllers"].values())}
    require(len(fresh_units) == 3 and not units & fresh_units, "STARTUP_RETRY_UNIT_REUSE")


def derived_request_ids(preparation_id):
    """Use the frozen assembly algorithm for all three query/management IDs."""
    assembly = helper("q2_prepare_assembly")
    return [assembly.digest(dict(preparation_id=preparation_id, phase=phase, role=role))[:32]
        for phase in assembly.PHASES for role in ("query", "management")]
