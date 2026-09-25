"""LOGIC_ONLY: protected declarations do not establish OS/capacity facts."""
import copy
import unittest

from local_hand_jobs import quota_contract as q, quota_grant as g, budget
from q2_fixtures import BOOT, SECOND, capacity, grant_data, make_grant, encoded


class GrantTests(unittest.TestCase):
    def test_full_origin_and_deterministic_request_with_no_circular_digest(self):
        grant = make_grant()
        value = grant.as_dict()
        self.assertEqual(grant.digest, grant.request.as_dict()["observation_grant_digest"])
        self.assertEqual(value["allocation"]["allocation_id"], grant.request.as_dict()["allocation_digest"])
        self.assertEqual("job-fixture-preflight", grant.request.as_dict()["execution_id"])
        value["budget"]["boot_id"] = "0" * 36
        self.assertEqual(BOOT, grant.as_dict()["budget"]["boot_id"])

    def test_wrong_original_bindings_and_nonfinite_management_rejected(self):
        paths = [("request", "allocation_digest"), ("request", "slot_ref"),
                 ("request", "execution_id"), ("request", "boot_id"),
                 ("endpoint", "boot_id"), ("management", "storage_bytes"),
                 ("management", "storage_inodes"), ("management", "receive_ns")]
        for parent, key in paths:
            data = grant_data()
            data[parent][key] = 0 if type(data[parent][key]) is int else "wrong"
            with self.subTest(key=key), self.assertRaises(q.QuotaError):
                g.decode_grant(encoded(data))
        for key in g._STAGE_KEYS:
            for wrong in (0, -1, True, None, q.MAX_INTEGER + 1):
                data = grant_data()
                data["management"]["stages"]["query"][key] = wrong
                with self.subTest(key=key, wrong=wrong), self.assertRaises(q.QuotaError):
                    g.decode_grant(encoded(data))

    def test_original_deadline_includes_receive_and_stop_without_renewal(self):
        data = grant_data()
        data["request"]["deadline_ns"] = 5 * SECOND  # needs >= 6 seconds
        with self.assertRaisesRegex(q.QuotaError, "MANAGEMENT_DEADLINE"):
            g.decode_grant(encoded(data))
        data["request"]["deadline_ns"] = 100 * SECOND
        with self.assertRaisesRegex(q.QuotaError, "ORIGINAL_BINDING"):
            g.decode_grant(encoded(data))

    def test_distinct_and_shared_domain_budget_is_not_mount_string_based(self):
        data = grant_data()
        data["budget"]["limits"]["reservation_bytes"] = 65536
        with self.assertRaisesRegex(q.QuotaError, "ROOT_BUDGET"):
            g.decode_grant(encoded(data))
        for root in data["roots"]:
            root["project_id"] = 1001
        grant = g.decode_grant(encoded(data))
        self.assertEqual(3, len(grant.as_dict()["roots"]))
        data["roots"][1]["hard_bytes"] = 1024
        with self.assertRaisesRegex(q.QuotaError, "DOMAIN_LIMIT_CONFLICT"):
            g.decode_grant(encoded(data))

    def test_retained_domain_capacity_and_management_are_both_finite(self):
        cap = capacity()
        grant = make_grant(declared_capacity=cap)
        self.assertEqual(2**20, g.check_capacity(cap, [grant])["storage_bytes"])
        for key in ("storage_bytes", "storage_inodes", "cpu_ns", "memory_bytes", "pids", "output_bytes"):
            small = capacity()
            small["management"][key] = g.totals(grant)[key] - 1
            bound = make_grant(declared_capacity=small)
            with self.subTest(key=key), self.assertRaisesRegex(q.QuotaError, "MANAGEMENT_EXHAUSTED"):
                g.check_capacity(small, [bound])
        cap["ceiling_bytes"] = cap["management"]["storage_bytes"]
        with self.assertRaisesRegex(q.QuotaError, "GLOBAL_CAPACITY"):
            g.decode_capacity(encoded(cap))

    def test_duplicate_domains_and_wrong_capacity_digest_do_not_borrow_space(self):
        cap = capacity()
        cap["domains"].append(copy.deepcopy(cap["domains"][0]))
        with self.assertRaisesRegex(q.QuotaError, "DUPLICATE_DOMAIN"):
            g.decode_capacity(encoded(cap))
        cap = capacity()
        cap["retained_bytes"] += 1
        with self.assertRaisesRegex(q.QuotaError, "CAPACITY_BINDING"):
            g.check_capacity(cap, [make_grant()])
        with self.assertRaisesRegex(q.QuotaError, "MANAGEMENT_REUSE"):
            g.check_capacity(capacity(), [make_grant(), make_grant()])

    def test_bootstrap_binding_and_strict_versions(self):
        grant = make_grant()
        data = grant.as_dict()
        execution = {"execution_id": data["request"]["execution_id"], "phase": "preflight",
            "operation_id": "fixture", "quota_grant_digest": grant.digest,
            "budget_grant": data["budget"], "budgets": data["budget"]["limits"],
            "phase_deadline_boottime_ns": data["request"]["deadline_ns"]}
        self.assertEqual(grant, g.check_execution(grant, execution, data["allocation"], now_ns=2*SECOND))
        for key in execution:
            changed = copy.deepcopy(execution)
            changed[key] = None
            with self.subTest(key=key), self.assertRaises(q.QuotaError):
                g.check_execution(grant, changed, data["allocation"], now_ns=2*SECOND)
        for change in ({"schema": "unknown"}, {"extra": True}):
            with self.assertRaises(q.QuotaError):
                g.decode_grant(encoded(dict(data, **change)))

    def test_legacy_substage_cpu_shares_are_unchanged(self):
        phase = make_grant().as_dict()["budget"]
        self.assertEqual([4, 5], [budget.substage_limits(phase, name, supervision_version=2)["cpu_seconds"] for name in ("bootstrap", "helper")])
        self.assertEqual([3, 3, 3], [budget.substage_limits(phase, name, supervision_version=3)["cpu_seconds"] for name in ("bootstrap", "helper", "result_reader")])
