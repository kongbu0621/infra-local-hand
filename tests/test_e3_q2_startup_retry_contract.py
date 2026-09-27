"""Synthetic contract cases: no guest reads, provisioning or live execution."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest("Synthetic inherited Q2 fixtures require Unix paths")

from test_e3_quota_q2_retry_contract import fixture as previous_fixture

spec = importlib.util.spec_from_file_location("_startup_retry_contract_tests",
    Path(__file__).parent / "e3_host/q2_startup_retry_contract.py")
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)


def fixture():
    """Return original, previous CPUQuota plan, new strictly distinct plan."""
    original, previous = previous_fixture()
    previous["source"].update(commit=r.PREVIOUS_SOURCE_COMMIT, tree=r.PREVIOUS_SOURCE_TREE)
    historical = r.legacy.bind(original, previous)
    first = dict(kind=r.PREDECESSOR_KINDS[0], plan_path=previous["original_plan_path"],
        plan_sha256=previous["original_plan_sha256"], prepared_path=previous["old_prepared"],
        handoff_path=previous["old_handoff"], owner_output=previous["old_owner_output"],
        ledger=copy.deepcopy(previous["old_ledger"]),
        policy_path=original["directories"]["authority"]["path"] + "/policy.json",
        failed_units=[dict(role=role, unit="lhq" + token + ".service", invocation_id=digit * 32,
            exec_main_code=1, exec_main_status=3) for role, token, digit in
            (("preparation", original["preparation_id"], "3"),
             ("recovery", Path(previous["old_prepared"]).parent.name, "4"))])
    previous_path = str(Path(previous["candidate"]["source"]).parent / "retry.json")
    second = dict(kind=r.PREDECESSOR_KINDS[1], plan_path=previous_path,
        plan_sha256=r.sha(r.encoded(previous)),
        prepared_path=previous["directories"]["reservation"]["path"] + "/prepared.json",
        handoff_path=previous["directories"]["reservation"]["path"] + "/handoff.json",
        owner_output=previous["directories"]["capture"]["path"] + "/owner_output",
        policy_path=previous["directories"]["authority"]["path"] + "/policy.json",
        ledger=dict(path=previous["directories"]["state"]["path"] + "/jobs.sqlite", device=11, inode=1000,
            uid=original["account"]["uid"], mode=0o600, ledger_id=previous["settings"]["identity"]["ledger_id"],
            generation=[1, 1]),
        failed_units=[dict(role=role, unit=unit, invocation_id=digit * 32, exec_main_code=1, exec_main_status=3)
            for role, unit, digit in (("service", previous["service"], "7"),
                ("supervisor", previous["settings"]["controllers"]["supervisor"]["unit"], "8"))])
    settings = copy.deepcopy(previous["settings"])
    settings["identity"].update(id="9" * 32, authority_id="startup-authority",
        install_uuid="22345678-1234-4234-8234-123456789abc", operation_id="bbcdef01-1234-4234-9234-123456789abc",
        epoch="a" * 32, slot_generation="b" * 32, session="8" * 64, ledger_id="startup-ledger", deployment_epoch=3)
    for role, control in settings["controllers"].items(): control["unit"] = "lhqstartup" + role + ".service"
    directories = copy.deepcopy(original["directories"])
    for role, item in directories.items():
        if role not in r.REUSED_DIRECTORIES: item["path"] += "-startup"
    value = dict(schema=r.SCHEMA, scope=r.SCOPE, rule=r.RULE, baseline=r.BASELINE, closure=r.CLOSURE,
        owner_decision=r.OWNER_DECISION, attempt_id="startup001", original_plan_path=first["plan_path"],
        original_plan_sha256=first["plan_sha256"], old_files=copy.deepcopy(previous["old_files"]),
        predecessors=[first, second], reservations=[], source=dict(commit="c" * 40, tree="d" * 40,
            files={"/synthetic/startup-tools/" + name: "e" * 64 for name in r.REQUIRED_SOURCE_FILES}),
        candidate=dict(source="/synthetic/startup-input/source", wheel="/synthetic/startup-input/candidate.whl",
            destination="/synthetic/system/installation-startup", commit=r.CANDIDATE_COMMIT,
            tree=r.CANDIDATE_TREE, wheel_sha256=r.CANDIDATE_WHEEL_SHA256),
        directories=directories, settings=settings, retained_inputs=copy.deepcopy(previous["retained_inputs"]),
        service="lhqstartup001.service")
    for item, old in zip(value["predecessors"], (original, historical)):
        value["old_files"].update({item[key]: "a" * 64 for key in ("prepared_path", "handoff_path", "policy_path")
            if item[key] not in value["old_files"]})
        value["old_files"][item["plan_path"]] = item["plan_sha256"]
        value["old_files"][item["ledger"]["path"]] = "b" * 64
        for name in r.OWNER_FILES:
            value["old_files"].setdefault(item["owner_output"] + "/" + name, "a" * 64)
        for name in ("authority.json", "manifest.json"):
            value["old_files"][str(Path(item["prepared_path"]).parent / name)] = "a" * 64
        value["old_files"][old["directories"]["declarations"]["path"] + "/owner_declarations/envelope.json"] = "a" * 64
    for item, names in ((first, ("first-request-issuance.json", "first-request.json")), (second, r.STARTUP_RECORDS)):
        for name in names: value["old_files"][str(Path(item["prepared_path"]).parent / name)] = "a" * 64
    value["reservations"] = r.required_reservations(original, historical, value,
        recovery_stage="/synthetic/recovery-tools/stage.json")
    for row in value["reservations"]:
        value["old_files"].setdefault(row["path"], "a" * 64)
    value["old_files"][original["directories"]["reservation"]["path"] + "/intent.json"] = first["plan_sha256"]
    value["retained_inputs"].append(dict(path=previous["candidate"]["destination"], category="installation"))
    for role, item in previous["directories"].items():
        if role not in r.REUSED_DIRECTORIES:
            value["retained_inputs"].append(dict(path=item["path"], category=r._category(role)))
    value["retained_inputs"].extend(dict(path=path, category="installation") for path in
        ("/synthetic/input.intent.json", "/synthetic/staged.intent.json", "/synthetic/recovery-tools",
         "/synthetic/startup-input", "/synthetic/startup-tools"))
    return original, previous, value


def decode(value):
    raw = r.encoded(value)
    return r.decode(raw, r.sha(raw))


def bind(original, previous, value):
    return r.bind(original, value, previous)


class StartupRetryContract(unittest.TestCase):
    def test_exact_dual_history_binds_without_changing_any_input_or_resource(self):
        original, previous, value = fixture()
        before = tuple(r.encoded(x) for x in (original, previous, value))
        result = r.bind(original, decode(value), previous)
        self.assertEqual(before, tuple(r.encoded(x) for x in (original, previous, value)))
        self.assertEqual(r.SCHEMA, result["schema"])
        self.assertEqual("ISOLATED_Q2_SUPERVISOR_STARTUP_RETRY", result["purpose"])
        self.assertEqual(140, result["budgets"]["preparation_seconds"])
        for key in ("host", "account", "roots", "parents", "retained", "retained_domains", "tools", "mounts"):
            self.assertEqual(original[key], result[key])
        for key in original["budgets"]:
            if key != "preparation_seconds": self.assertEqual(original["budgets"][key], result["budgets"][key])
        result["roots"][0]["project_id"] += 1
        self.assertEqual(before, tuple(r.encoded(x) for x in (original, previous, value)))

    def test_authority_and_frozen_runtime_are_exact(self):
        for field in ("schema", "scope", "rule", "baseline", "closure", "owner_decision"):
            *_, value = fixture(); value[field] = "wrong"
            with self.subTest(field=field), self.assertRaises(ValueError): decode(value)
        for field in ("commit", "tree", "wheel_sha256"):
            *_, value = fixture(); value["candidate"][field] = "0" * len(value["candidate"][field])
            with self.subTest(field=field), self.assertRaises(ValueError): decode(value)

    def test_old_schema_extra_fields_and_noninteger_json_are_rejected(self):
        _, previous, value = fixture()
        with self.assertRaises(ValueError): decode(previous)
        value["reset_failed"] = False
        with self.assertRaises(ValueError): decode(value)
        for raw in (b'{"a":1,"a":2}', b'{"a":1.0}', b'{"a":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): r.decode(raw, r.sha(raw))

    def test_each_predecessor_plan_is_independently_digest_decoded(self):
        for which in (0, 1):
            original, previous, value = fixture()
            (original if which == 0 else previous)["settings"]["identity"]["expires_at"] += 1
            with self.subTest(which=which), self.assertRaises(ValueError): bind(original, previous, value)
        original, previous, value = fixture()
        previous["source"]["commit"] = "9" * 40
        value["predecessors"][1]["plan_sha256"] = r.sha(r.encoded(previous))
        value["old_files"][value["predecessors"][1]["plan_path"]] = value["predecessors"][1]["plan_sha256"]
        with self.assertRaisesRegex(ValueError, "PREVIOUS_SOURCE"): bind(original, previous, value)

    def test_history_type_order_count_and_every_required_pin_are_enforced(self):
        for change in (lambda v: v["predecessors"].reverse(), lambda v: v["predecessors"].pop(),
                lambda v: v["predecessors"].append(copy.deepcopy(v["predecessors"][1]))):
            *_, value = fixture(); change(value)
            with self.assertRaises(ValueError): decode(value)
        original, previous, value = fixture()
        for path in value["old_files"]:
            changed = copy.deepcopy(value); del changed["old_files"][path]
            with self.subTest(path=path), self.assertRaises(ValueError): bind(original, previous, changed)

    def test_prior_pins_cannot_be_replaced_even_with_new_plan_digest(self):
        original, previous, value = fixture()
        path = previous["old_owner_output"] + "/result.json"
        value["old_files"][path] = "f" * 64
        with self.assertRaisesRegex(ValueError, "HISTORY_PIN_CHANGED"): bind(original, previous, value)

    def test_ledger_alias_substitution_and_boolean_identity_are_rejected(self):
        for field, supplied in (("path", "/synthetic/foreign.sqlite"), ("uid", 1101),
                ("ledger_id", "wrong-ledger"), ("generation", [1, 2]), ("device", True), ("mode", True)):
            original, previous, value = fixture(); value["predecessors"][1]["ledger"][field] = supplied
            with self.subTest(field=field), self.assertRaises(ValueError): bind(original, previous, value)
        *_, value = fixture(); value["predecessors"][1]["ledger"]["inode"] = value["predecessors"][0]["ledger"]["inode"]
        with self.assertRaisesRegex(ValueError, "LEDGER_ALIAS"): decode(value)

    def test_failed_allowlist_is_exactly_the_known_second_service_and_supervisor(self):
        for field, supplied in (("unit", "lhqunrelated.service"), ("exec_main_status", 0),
                ("exec_main_code", True), ("invocation_id", "0" * 32), ("role", "target")):
            original, previous, value = fixture(); value["predecessors"][1]["failed_units"][0][field] = supplied
            with self.subTest(field=field), self.assertRaises(ValueError): bind(original, previous, value)
        *_, value = fixture(); value["predecessors"][0]["failed_units"] = value["predecessors"][1]["failed_units"]
        with self.assertRaises(ValueError): decode(value)

    def test_all_prior_identity_fields_and_cross_field_values_are_reserved(self):
        for predecessor in (0, 1):
            for key in r.FRESH_IDENTITIES:
                original, previous, value = fixture()
                value["settings"]["identity"][key] = (original if predecessor == 0 else previous)["settings"]["identity"][key]
                with self.subTest(predecessor=predecessor, key=key), self.assertRaises(ValueError): bind(original, previous, value)
        original, previous, value = fixture()
        value["settings"]["identity"]["id"] = previous["settings"]["identity"]["epoch"]
        with self.assertRaisesRegex(ValueError, "IDENTITY_REUSE"): bind(original, previous, value)
        original, previous, value = fixture(); value["settings"]["identity"]["deployment_epoch"] = 2
        with self.assertRaises(ValueError): bind(original, previous, value)

    def test_all_prior_attempts_units_and_original_principals_are_reserved(self):
        original, previous, value = fixture()
        for unit in (previous["service"], previous["settings"]["controllers"]["target"]["unit"],
                original["settings"]["controllers"]["supervisor"]["unit"], "lhqrecovery001.service"):
            changed = copy.deepcopy(value); changed["service"] = unit
            with self.subTest(unit=unit), self.assertRaises(ValueError): bind(original, previous, changed)
        for field in ("node_id", "profile_ref", "principal_id"):
            changed = copy.deepcopy(value); changed["settings"]["identity"][field] += "-new"
            with self.subTest(field=field), self.assertRaises(ValueError): bind(original, previous, changed)
        value["attempt_id"] = previous["attempt_id"]
        with self.assertRaises(ValueError): bind(original, previous, value)

    def test_generated_query_management_ids_and_failed_invocations_cannot_be_reused(self):
        original, previous, value = fixture()
        tokens = r.derived_request_ids(previous["settings"]["identity"]["id"])
        tokens.extend(row["invocation_id"] for predecessor in value["predecessors"] for row in predecessor["failed_units"])
        for token in tokens:
            changed = copy.deepcopy(value); changed["settings"]["identity"]["id"] = token
            with self.subTest(token=token), self.assertRaisesRegex(ValueError, "IDENTITY_REUSE"):
                bind(original, previous, changed)

    def test_original_limits_cannot_change_in_either_direction(self):
        for section, key, delta in (("owner", "cpu_ns", 1), ("owner", "runtime_ns", -1),
                ("original_budgets", "log_bytes", 1), ("management", "storage_inodes", 1),
                ("capacity_management", "storage_bytes", 4096), ("limits", "requests_per_minute", 1)):
            original, previous, value = fixture(); value["settings"][section][key] += delta
            with self.subTest(section=section, key=key), self.assertRaises(ValueError): bind(original, previous, value)

    def test_neither_history_paths_nor_new_staging_can_be_overlaid(self):
        original, previous, value = fixture()
        for target in (previous["candidate"]["destination"], previous["candidate"]["source"] + "/new",
                previous["directories"]["state"]["path"] + "/new", original["directories"]["capture"]["path"],
                "/outside/installation", original["directories"]["profile_work"]["path"] + "/new"):
            changed = copy.deepcopy(value); changed["candidate"]["destination"] = target
            with self.subTest(target=target), self.assertRaises(ValueError): bind(original, previous, changed)
        changed = copy.deepcopy(value); changed["candidate"]["source"] = previous["candidate"]["source"]
        with self.assertRaises(ValueError): bind(original, previous, changed)

    def test_staging_cannot_exempt_history_from_snapshots(self):
        original, previous, value = fixture()
        value["candidate"]["source"] = "/synthetic/input/new/source"
        value["candidate"]["wheel"] = "/synthetic/input/new/candidate.whl"
        value["retained_inputs"] = [x for x in value["retained_inputs"] if x["path"] != "/synthetic/startup-input"]
        with self.assertRaises(ValueError): bind(original, previous, value)

    def test_every_prior_and_new_cost_domain_needs_unique_accounting_coverage(self):
        original, previous, value = fixture()
        for index in range(len(value["retained_inputs"])):
            changed = copy.deepcopy(value); del changed["retained_inputs"][index]
            with self.subTest(index=index), self.assertRaises(ValueError): bind(original, previous, changed)
        changed = copy.deepcopy(value); changed["retained_inputs"].append(dict(path="/synthetic/staged/source", category="installation"))
        with self.assertRaisesRegex(ValueError, "RETAINED_ALIAS"): decode(changed)

    def test_each_historical_reservation_kind_is_required_and_bound(self):
        original, previous, value = fixture()
        self.assertEqual(10, len(value["reservations"]))
        for index, row in enumerate(value["reservations"]):
            changed = copy.deepcopy(value); del changed["reservations"][index]
            with self.subTest(kind=row["kind"]), self.assertRaises(ValueError): decode(changed)
        changed = copy.deepcopy(value)
        owners = [x for x in changed["reservations"] if x["kind"] == "OWNER_COMMITMENT"]
        owners[0]["covered_paths"] = owners[1]["covered_paths"]
        with self.assertRaisesRegex(ValueError, "RESERVATION_BINDING"): bind(original, previous, changed)
        changed = copy.deepcopy(value); changed["reservations"][0]["category"] = "installation"
        with self.assertRaises(ValueError): decode(changed)
        changed = copy.deepcopy(value); changed["reservations"][0]["released"] = True
        with self.assertRaises(ValueError): decode(changed)

    def test_reservation_record_hashes_and_original_intent_are_immutable(self):
        original, previous, value = fixture()
        path = original["directories"]["reservation"]["path"] + "/intent.json"
        value["old_files"][path] = "f" * 64
        with self.assertRaisesRegex(ValueError, "ORIGINAL_INTENT"): bind(original, previous, value)

    def test_compilation_source_closure_is_required_without_runtime_overlap(self):
        for filename in r.REQUIRED_SOURCE_FILES:
            *_, value = fixture(); del value["source"]["files"]["/synthetic/startup-tools/" + filename]
            with self.subTest(filename=filename), self.assertRaises(ValueError): decode(value)
        original, previous, value = fixture()
        value["source"]["commit"] = previous["source"]["commit"]
        with self.assertRaisesRegex(ValueError, "ORCHESTRATION_REUSE"): bind(original, previous, value)


if __name__ == "__main__": unittest.main()
