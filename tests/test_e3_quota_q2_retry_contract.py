"""The replacement contract cannot launder an old issuance or enlarge limits."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest("Linux retry contract fixtures require Unix identity and paths")

from test_e3_quota_q2_prepare_contract import fixture as plan_fixture
from test_e3_quota_q2_prepare_driver import fixture as driver_fixture

spec = importlib.util.spec_from_file_location("_retry_contract_tests", Path(__file__).parent / "e3_host/q2_retry_contract.py")
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)


def fixture():
    original = plan_fixture()
    original["settings"] = copy.deepcopy(driver_fixture()[0]["settings"])
    original["candidate"].update(commit=r.OLD_COMMIT, tree=r.OLD_TREE, wheel_sha256=r.OLD_WHEEL_SHA256)
    for root in original["roots"]: root.update(hard_bytes=1024**2, inode_hard_limit=128)
    original["retained_domains"] = [dict(project_id=10001+i, hard_bytes=mib*1024**2, inode_hard_limit=4096)
                                    for i, mib in enumerate((64, 64, 4, 64))]
    settings = copy.deepcopy(original["settings"])
    settings["identity"].update(id="d"*32, authority_id="retry-authority", install_uuid="12345678-1234-4234-8234-123456789abc",
        operation_id="abcdef01-1234-4234-9234-123456789abc", epoch="e"*32, slot_generation="f"*32,
        session="b"*64, ledger_id="retry-ledger", deployment_epoch=2, generation=1)
    for role, control in settings["controllers"].items(): control["unit"] = "lhqretry" + role + ".service"
    directories = copy.deepcopy(original["directories"])
    for role, item in directories.items():
        if role not in r.REUSED_DIRECTORIES: item["path"] += "-retry"
    candidate = dict(source="/synthetic/staged/source", wheel="/synthetic/staged/candidate.whl",
        destination="/synthetic/system/installation-retry", commit=r.CANDIDATE_COMMIT, tree=r.CANDIDATE_TREE,
        wheel_sha256=r.CANDIDATE_WHEEL_SHA256)
    plan_path = "/synthetic/input/plan.json"
    record_path = original["directories"]["reservation"]["path"] + "/recovery001"
    old_owner = original["directories"]["capture"]["path"] + "/owner_output"
    ledger = dict(path=original["directories"]["state"]["path"] + "/jobs.sqlite", device=11, inode=999,
        mode=0o600, uid=original["account"]["uid"], ledger_id=original["settings"]["identity"]["ledger_id"], generation=[1,1])
    old_files = {str(Path(old_owner) / name): "1"*64 for name in r.OWNER_FILES}
    old_files.update({record_path + "/" + name: "2"*64 for name in ("prepared.json", "handoff.json", "recovery-result.json")})
    old_files[plan_path] = r.sha(r.encoded(original))
    old_files[original["directories"]["authority"]["path"] + "/policy.json"] = "3"*64
    retained = [dict(path="/synthetic/input", category="installation"),
                dict(path=original["candidate"]["destination"], category="installation"),
                dict(path="/synthetic/staged", category="installation"),
                dict(path="/synthetic/retry-tools", category="installation")]
    for role, item in original["directories"].items():
        if role not in r.REUSED_DIRECTORIES:
            category = "journal" if role == "journal" else "capture" if role in ("capture", "declarations") else "state"
            retained.append(dict(path=item["path"], category=category))
    return original, dict(schema=r.SCHEMA, scope=r.SCOPE, baseline=r.BASELINE, closure=r.CLOSURE,
        attempt_id="retry001", original_plan_sha256=old_files[plan_path], original_plan_path=plan_path,
        old_files=old_files, old_prepared=record_path+"/prepared.json", old_handoff=record_path+"/handoff.json",
        old_owner_output=old_owner, old_ledger=ledger,
        source=dict(commit="7"*40, tree="8"*40, files={"/synthetic/retry-tools/" + name: "9"*64
            for name in ("q2_retry.py", "q2_retry_contract.py", "q2_retry_driver.py", "q2_retry_delivery.py")}),
        candidate=candidate, directories=directories, settings=settings, retained_inputs=retained,
        service="lhqretry001.service")


def decode(retry):
    raw = r.encoded(retry)
    return r.decode(raw, r.sha(raw))


class RetryContract(unittest.TestCase):
    def test_binding_preserves_old_bytes_and_all_physical_roots(self):
        old, retry = fixture(); before = r.encoded(old), r.encoded(retry)
        derived = r.bind(old, decode(retry))
        self.assertEqual(before, (r.encoded(old), r.encoded(retry)))
        self.assertEqual(derived["schema"], r.SCHEMA)
        self.assertNotEqual(derived["scope"], old["scope"])
        self.assertEqual(140, derived["budgets"]["preparation_seconds"])
        self.assertEqual("retry001", derived["preparation_id"])
        for key in ("host", "account", "roots", "parents", "retained", "retained_domains", "tools", "mounts"):
            self.assertEqual(old[key], derived[key])
        self.assertNotIn(retry["old_ledger"]["path"], retry["old_files"])
        derived["roots"][0]["project_id"] += 1
        self.assertEqual(before, (r.encoded(old), r.encoded(retry)))

    def test_wrong_authority_candidate_and_extra_fields_rejected(self):
        for field in ("schema", "scope", "baseline", "closure"):
            _, retry = fixture(); retry[field] = "wrong"
            with self.subTest(field=field), self.assertRaises(ValueError): decode(retry)
        for field in ("commit", "tree", "wheel_sha256"):
            _, retry = fixture(); retry["candidate"][field] = "0"*len(retry["candidate"][field])
            with self.subTest(field=field), self.assertRaises(ValueError): decode(retry)
        _, retry = fixture(); retry["replay"] = True
        with self.assertRaises(ValueError): decode(retry)

    def test_duplicate_float_and_boolean_integer_do_not_decode(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":1.1}', b'{"a":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): r.decode(raw, r.sha(raw))
        for key, value in (("generation", [True,1]), ("device", True), ("mode", True)):
            _, retry = fixture(); retry["old_ledger"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): decode(retry)

    def test_incomplete_historical_evidence_rejected(self):
        old, retry = fixture()
        for filename in list(retry["old_files"]):
            changed = copy.deepcopy(retry); del changed["old_files"][filename]
            with self.subTest(filename=filename), self.assertRaises(ValueError): r.bind(old, changed)

    def test_ledger_and_prepared_location_cannot_be_substituted(self):
        for key, value in (("path", "/synthetic/other/jobs.sqlite"), ("uid", 1101), ("ledger_id", "another"), ("generation", [1,2])):
            old, retry = fixture(); retry["old_ledger"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): r.bind(old, retry)
        old, retry = fixture(); retry["old_prepared"] = retry["old_handoff"]
        with self.assertRaises(ValueError): r.bind(old, retry)

    def test_original_plan_digest_and_fixed_candidate_bind_before_effects(self):
        old, retry = fixture(); old["host"]["hostname"] = "another-guest"
        with self.assertRaises(ValueError): r.bind(old, retry)
        old, retry = fixture(); old["candidate"]["commit"] = "a"*40
        retry["original_plan_sha256"] = retry["old_files"][retry["original_plan_path"]] = r.sha(r.encoded(old))
        with self.assertRaisesRegex(ValueError, "RETRY_OLD_CANDIDATE"): r.bind(old, retry)

    def test_new_identity_and_controller_units_cannot_reuse_issued_old_values(self):
        for field in r.FRESH_IDENTITIES + ("deployment_epoch",):
            old, retry = fixture(); retry["settings"]["identity"][field] = old["settings"]["identity"][field]
            with self.subTest(field=field), self.assertRaises(ValueError): r.bind(old, retry)
        old, retry = fixture(); retry["settings"]["controllers"]["target"]["unit"] = old["settings"]["controllers"]["target"]["unit"]
        with self.assertRaises(ValueError): r.bind(old, retry)
        old, retry = fixture(); retry["service"] = retry["settings"]["controllers"]["target"]["unit"]
        with self.assertRaises(ValueError): r.bind(old, retry)
        old, retry = fixture(); retry["attempt_id"] = "recovery001"
        with self.assertRaises(ValueError): r.bind(old, retry)
        old, retry = fixture(); retry["service"] = "lhqrecovery001.service"
        with self.assertRaises(ValueError): r.bind(old, retry)

    def test_original_limits_cannot_increase_or_silently_shrink(self):
        for section, field, delta in (("owner", "cpu_ns", 1), ("owner", "runtime_ns", -1),
                ("original_budgets", "log_bytes", 1), ("capacity_management", "storage_bytes", 4096),
                ("limits", "requests_per_minute", 1)):
            old, retry = fixture(); retry["settings"][section][field] += delta
            with self.subTest(section=section,field=field), self.assertRaises(ValueError): r.bind(old, retry)

    def test_old_and_staged_costs_cannot_be_omitted_or_double_charged(self):
        old, retry = fixture()
        for index in range(len(retry["retained_inputs"])):
            changed = copy.deepcopy(retry); del changed["retained_inputs"][index]
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "RETRY_ACCOUNTING_COVERAGE"):
                r.bind(old, changed)
        old, retry = fixture(); retry["retained_inputs"].append(dict(path="/synthetic/staged/source", category="installation"))
        with self.assertRaisesRegex(ValueError, "RETRY_RETAINED_ALIAS"): r.bind(old, retry)
        old, retry = fixture(); retry["retained_inputs"][0]["category"] = "state"
        with self.assertRaisesRegex(ValueError, "RETRY_ACCOUNTING_COVERAGE"): r.bind(old, retry)
        # A shared accounting ancestor must not classify old source as mutable
        # new staging and thereby exempt it from the preserved snapshot.
        old, retry = fixture()
        retry["candidate"]["source"] = "/synthetic/input/new/source"
        retry["candidate"]["wheel"] = "/synthetic/input/new/candidate.whl"
        retry["retained_inputs"] = [item for item in retry["retained_inputs"] if item["path"] != "/synthetic/staged"]
        with self.assertRaisesRegex(ValueError, "RETRY_MIXED_OLD_NEW_STAGING"): r.bind(old, retry)

    def test_new_paths_cannot_overwrite_old_or_reused_quota_objects(self):
        for target in ("/synthetic/system/state", "/synthetic/system/state/new", "/synthetic/old/new",
                       "/synthetic/quota/profile_work/new", "/synthetic/staged/new"):
            old, retry = fixture(); retry["candidate"]["destination"] = target
            with self.subTest(target=target), self.assertRaises(ValueError): r.bind(old, retry)
        old, retry = fixture(); retry["directories"]["profile_work"]["path"] += "-new"
        with self.assertRaises(ValueError): r.bind(old, retry)
        for key, value in (("path", "/outside/state-retry"), ("filesystem", "evidence"),
                           ("owner", "root"), ("mode", 0o755)):
            old, retry = fixture(); retry["directories"]["state"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): r.bind(old, retry)

    def test_root_limits_and_retained_q1_commitments_stay_fixed(self):
        for kind in ("root", "q1"):
            old, retry = fixture()
            if kind == "root": old["roots"][0]["hard_bytes"] += 4096
            else: old["retained_domains"][0]["hard_bytes"] -= 4096
            retry["original_plan_sha256"] = retry["old_files"][retry["original_plan_path"]] = r.sha(r.encoded(old))
            with self.subTest(kind=kind), self.assertRaises(ValueError): r.bind(old, retry)

    def test_tools_cannot_overlay_frozen_runtime_or_old_source(self):
        for stage in ("/synthetic/staged/source", "/synthetic/input/source", "/synthetic/system/state-retry"):
            old, retry = fixture(); retry["source"]["files"] = {stage + "/" + Path(k).name:v for k,v in retry["source"]["files"].items()}
            with self.subTest(stage=stage), self.assertRaises(ValueError): r.bind(old, retry)
        for revision in (r.BASELINE, r.CLOSURE, r.CANDIDATE_COMMIT, r.OLD_COMMIT):
            old, retry = fixture(); retry["source"]["commit"] = revision
            with self.subTest(revision=revision), self.assertRaises(ValueError): r.bind(old, retry)


if __name__ == "__main__": unittest.main()
