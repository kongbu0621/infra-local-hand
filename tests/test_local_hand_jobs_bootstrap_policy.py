"""Private slot admission is pure metadata, never a filesystem probe."""
import copy
import unittest
from unittest import mock

from local_hand_jobs.contract import JobError
from local_hand_jobs.policy import Policy
from test_local_hand_jobs_policy import policy_fixture


def configured():
    config = policy_fixture("/synthetic")
    config["process_manager"] = {"uid": 1000, "slice": "fixture.slice", "cgroup": "/sys/fs/cgroup/fixture"}
    profile = config["profiles"]["fixture"]
    profile["bootstrap_slots"] = [{"slot_id": "slot-1", "roots": {
        name: {"path": profile[name + "_root"] + "/slot-1", "device": 1, "inode": index + 1, "uid": 1000}
        for index, name in enumerate(("work", "evidence", "temporary"))}}]
    profile["bootstrap_evidence_store"] = {"path": "/synthetic/sealed", "device": 1, "inode": 100, "uid": 1000}
    return config


class BootstrapPolicyTests(unittest.TestCase):
    def test_admission_does_not_probe_paths_and_changes_the_policy_binding(self):
        config = configured()
        with mock.patch("pathlib.Path.stat", side_effect=AssertionError("admission must not read storage")):
            admitted = Policy(config)
        old = policy_fixture("/synthetic")
        self.assertNotEqual(admitted.policy_digest, Policy(old).policy_digest)

    def test_extra_writer_cannot_enter_control_source_or_active_roots(self):
        original = configured()
        for path in ("/synthetic/broker/store", "/synthetic/authority", "/synthetic/legacy/store",
                     "/synthetic/source", "/synthetic/python", "/synthetic/work/slot-1",
                     "/synthetic/work", "/synthetic/synthetic-archive", "/synthetic"):
            config = copy.deepcopy(original)
            config["profiles"]["fixture"]["bootstrap_evidence_store"]["path"] = path
            with self.subTest(path=path), self.assertRaises(JobError) as error: Policy(config)
            self.assertEqual(error.exception.code, "UNAUTHORIZED")

    def test_slots_require_exact_account_and_strictly_descendant_paths(self):
        original = configured()
        for changes in ({"uid": 1001}, {"path": "/synthetic/work"}, {"path": "/synthetic/work/../other"},
                        {"inode": True}, {"device": -1}, {"path": "/synthetic/work/with space"}):
            config = copy.deepcopy(original)
            config["profiles"]["fixture"]["bootstrap_slots"][0]["roots"]["work"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(JobError): Policy(config)

    def test_cross_profile_inode_alias_and_slot_store_alias_are_rejected(self):
        original = configured()
        for kind in ("profile_alias", "store_alias"):
            config = copy.deepcopy(original)
            if kind == "profile_alias":
                other = copy.deepcopy(config["profiles"]["fixture"])
                other.pop("bootstrap_evidence_store")
                for name in ("work", "evidence", "temporary"):
                    other[name + "_root"] += "-other"
                    other["bootstrap_slots"][0]["roots"][name]["path"] = other[name + "_root"] + "/slot-2"
                config["profiles"]["other"] = other
            else:
                config["profiles"]["fixture"]["bootstrap_evidence_store"]["inode"] = 1
            with self.subTest(kind=kind), self.assertRaises(JobError): Policy(config)

    def test_store_cannot_alias_another_profiles_work_tree(self):
        config = configured()
        other = copy.deepcopy(config["profiles"]["fixture"])
        other.pop("bootstrap_evidence_store"); other.pop("bootstrap_slots")
        other["resource_ids"] = ["other-resource"]
        for name in ("work", "evidence", "temporary"):
            other[name + "_root"] += "-other"
        config["profiles"]["other"] = other
        config["profiles"]["fixture"]["bootstrap_evidence_store"]["path"] = other["work_root"]
        with self.assertRaises(JobError): Policy(config)

    def test_admitted_nas_identity_cannot_be_a_local_slot_or_evidence_store(self):
        for target in ("slot", "store"):
            config = configured()
            profile = config["profiles"]["fixture"]
            root = (profile["bootstrap_evidence_store"] if target == "store"
                    else profile["bootstrap_slots"][0]["roots"]["work"])
            archive = profile["storages"]["storage"]["stable_mount_binding"]
            root.update(device=archive["device"], inode=archive["inode"])
            with self.subTest(target=target), self.assertRaises(JobError): Policy(config)
