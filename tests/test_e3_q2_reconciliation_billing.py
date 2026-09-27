"""Independent accounting counterexamples; no host/guest acceptance claim."""
import copy
import importlib.util
from pathlib import Path
import stat
import unittest

spec = importlib.util.spec_from_file_location("_reconciliation_bill_tests",
    Path(__file__).parent / "e3_host/q2_reconciliation_billing.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    scans = {}; roots = {}; serial = 1

    def scan(root, category, allocated=0, count=1, device=1):
        nonlocal serial
        entries = []
        for index in range(count):
            info = dict(device=device, inode=serial, st_mode=(stat.S_IFDIR | 0o700) if index == 0
                else (stat.S_IFREG | 0o600), uid=0, gid=0, nlink=1, size=0,
                blocks=allocated // 512 if index == 0 else 0, atime_ns=1, mtime_ns=1, ctime_ns=1)
            serial += 1
            entry = dict(relative_path="." if index == 0 else "file-" + str(index),
                type="directory" if index == 0 else "file", source_metadata=info)
            if index:
                entry["sha256"] = "a" * 64
            entries.append(entry)
        scans[root] = dict(path=root, entries=entries, bytes=allocated, inodes=count,
            device=device, logical_bytes=0)
        roots[root] = category

    # Values are public review facts; names are synthetic, and the missing
    # second live target is deliberately represented only in this test model.
    scan("/old/install", "installation", 35450880, 659)
    scan("/old/stage", "installation", 10424320, 588)
    scan("/second/install", "installation")
    scan("/second/stage", "installation", 11071488, 610)
    scan("/recovery/stage", "installation", 290816, 17)
    for attempt in ("old", "second"):
        for suffix, category in (("capture", "capture"), ("declarations", "capture"), ("journal", "journal")):
            scan("/" + attempt + "/" + suffix, category, 4096)
    obligations = []
    for attempt, installment, staging in (("old", m.INSTALLATIONS[0], dict(bytes=18788352, inodes=0)),
            ("second", m.INSTALLATIONS[1], dict(bytes=11071488, inodes=608))):
        for role, commitment in (("install", installment), ("stage", staging), ("owner", m.OWNER_POOL)):
            shared = role == "owner"
            obligations.append(dict(id=attempt + "-" + role, category="capture" if shared else "installation",
                commitment=copy.deepcopy(commitment), evidence=["/evidence/" + attempt + "-" + role],
                covered_paths=["/" + attempt + "/" + name for name in ("capture", "declarations", "journal")]
                    if shared else ["/" + attempt + "/" + role],
                accounting_categories=["capture", "journal"] if shared else ["installation"]))
    obligations.append(dict(id="recovery-stage", category="installation", commitment=dict(bytes=290816, inodes=17),
        evidence=["/evidence/recovery"], covered_paths=["/recovery/stage"], accounting_categories=["installation"]))
    new = []
    for identity, category, commitment, paths, excluded in (
            ("new-installation", "installation", m.INSTALLATIONS[1], ["/new/install"], []),
            ("new-state", "state", m.BASE_STATE, ["/new/state"], ["/new/state/reconciliation"]),
            ("new-owner-pool", "capture", m.OWNER_POOL, ["/new/capture", "/new/declarations", "/new/journal"], []),
            ("reconciliation-state", "state", m.RECONCILIATION_STATE, ["/new/state/reconciliation"], []),
            ("new-staging", "installation", dict(bytes=0, inodes=0), ["/new/stage"], [])):
        new.append(dict(id=identity, category=category, commitment=copy.deepcopy(commitment), covered_paths=paths,
            excluded_paths=excluded, accounting_categories=["capture", "journal"] if identity == "new-owner-pool"
                else [category], devices=[1]))
    quotas = []; pins = []
    for index in range(11):
        hard = ([64, 64, 64, 4][index] if index < 4 else 1) * m.MIB
        pin = dict(uuid="synthetic-filesystem", project=index + 1, hard_bytes=hard,
            hard_inodes=4096 if index < 4 else 128)
        pins.append(pin)
        quotas.append(dict(pin, device=1, used_bytes=4096, used_inodes=1))
        scan("/quota/domain-" + str(index), "quota", 4096)
    args = dict(scans=scans, obligations=obligations, new_obligations=new, quotas=quotas,
        devices=[dict(device=1, available_bytes=2**32, free_inodes=100000)],
        installation_targets=["/old/install", "/second/install"], expected_roots=roots, quota_expected=pins)
    return args, scan


class ReconciliationBilling(unittest.TestCase):
    def test_review_lower_bound_and_only_two_target_balances_removed(self):
        args, _ = fixture(); original = copy.deepcopy(args)
        quote = m.quote_bill(**args)
        before = quote["before"]["categories"]["installation"]
        self.assertEqual(dict(bytes=365694976, inodes=17599), before["admitted"])
        self.assertFalse(before["within_ceiling"])
        self.assertEqual(dict(bytes=232984576, inodes=11628), quote["terminated_unspent"])
        self.assertEqual(dict(bytes=132710400, inodes=5971),
            quote["proposed_after"]["categories"]["installation"]["admitted"])
        self.assertEqual(quote["before"], quote["current"])
        self.assertTrue(quote["proposed_after"]["admissible"])
        self.assertEqual(original, args)

    def test_actual_below_equal_and_above_both_independent_commitment_dimensions(self):
        for allocated, count, expected_bytes, expected_inodes in (
                (0, 1, 201326592, 8191), (201326592, 8192, 0, 0),
                (201327104, 8193, 0, 0), (201327104, 1, 0, 8191), (0, 8193, 201326592, 0)):
            with self.subTest(allocated=allocated, count=count):
                args, scan = fixture()
                scan("/old/install", "installation", allocated, count)
                quote = m.quote_bill(**args)
                first = quote["obligations"][0]
                self.assertEqual(dict(bytes=allocated, inodes=count), first["actual"])
                self.assertEqual(dict(bytes=expected_bytes, inodes=expected_inodes), first["unspent"])
                self.assertGreaterEqual(quote["proposed_after"]["categories"]["installation"]["actual"]["bytes"], allocated)

    def test_staging_zero_reserved_inodes_and_second_actual_excess_still_count(self):
        args, _ = fixture(); quote = m.quote_bill(**args)
        first_stage, second_stage = quote["obligations"][1], quote["obligations"][4]
        self.assertEqual(588, first_stage["actual"]["inodes"])
        self.assertEqual(0, first_stage["unspent"]["inodes"])
        self.assertEqual(610, second_stage["actual"]["inodes"])
        self.assertEqual(0, second_stage["unspent"]["inodes"])
        self.assertEqual(8364032, first_stage["unspent"]["bytes"])
        for row in (first_stage, second_stage, quote["obligations"][6]):
            self.assertFalse(row["terminated_by_amendment"])

    def test_owner_shared_pool_counted_once_physically_with_category_worst_cases(self):
        args, _ = fixture(); quote = m.quote_bill(**args)
        after = quote["proposed_after"]
        old_owners = [row for row in quote["obligations"] if row["origin"] == "historical" and row["category"] == "capture"]
        self.assertEqual([3, 3], [row["coverage_count"] for row in old_owners])
        self.assertEqual(2 * (20 * m.MIB - 12288) + 20 * m.MIB,
            after["categories"]["capture"]["future"]["bytes"])
        self.assertEqual(after["categories"]["capture"]["future"], after["categories"]["journal"]["future"])
        self.assertEqual(after["future"], after["by_device"][1]["future"])
        # A raw cumulative second bootstrap number is not an independent future.
        args["obligations"][3]["commitment"]["bytes"] = 113274880
        with self.assertRaisesRegex(ValueError, "OLD_COMMITMENT"):
            m.quote_bill(**args)

    def test_old_target_identity_cannot_borrow_other_tree_actual(self):
        for replacement in ("/old/stage", "/second/install", "/old"):
            args, _ = fixture(); args["obligations"][0]["covered_paths"] = [replacement]
            with self.assertRaisesRegex(ValueError, "TARGET_BINDING"):
                m.quote_bill(**args)

    def test_missing_old_tree_and_scan_aliases_are_unknown_not_zero(self):
        args, _ = fixture(); del args["scans"]["/second/install"]
        with self.assertRaisesRegex(ValueError, "SCAN_COVERAGE"):
            m.quote_bill(**args)
        del args["expected_roots"]["/second/install"]
        with self.assertRaisesRegex(ValueError, "MISSING_OLD_TREE"):
            m.quote_bill(**args)
        args, _ = fixture()
        args["scans"]["/second/install"]["entries"][0]["source_metadata"]["inode"] = (
            args["scans"]["/old/install"]["entries"][0]["source_metadata"]["inode"])
        with self.assertRaisesRegex(ValueError, "ACTUAL_ALIAS"):
            m.quote_bill(**args)

    def test_new_install_growth_reduces_its_same_peak_not_old_target(self):
        args, scan = fixture(); before = m.quote_bill(**args)
        scan("/new/install", "installation", 16 * m.MIB, 100)
        grown = m.quote_bill(**args, sealed=True)
        self.assertEqual(before["proposed_after"]["total"], grown["current"]["total"])
        self.assertEqual(before["terminated_unspent"], grown["terminated_unspent"])
        self.assertEqual(48 * m.MIB,
            next(row for row in grown["obligations"] if row["id"] == "new-installation")["unspent"]["bytes"])

    def test_record_growth_is_remeasured_inside_separate_state_subbudget(self):
        args, _ = fixture(); before = m.quote_bill(**args)
        old_serial = 100000
        entries = []
        for offset, (relative, blocks) in enumerate(((".", 8), ("reconciliation", 8), ("reconciliation/seal.json", 8))):
            directory = relative != "reconciliation/seal.json"
            entry = dict(relative_path=relative, type="directory" if directory else "file", source_metadata=dict(
                device=1, inode=old_serial + offset, st_mode=(stat.S_IFDIR | 0o700) if directory else (stat.S_IFREG | 0o600),
                uid=0, gid=0, nlink=1, size=0, blocks=blocks, atime_ns=1, mtime_ns=1, ctime_ns=1))
            if not directory:
                entry["sha256"] = "b" * 64
            entries.append(entry)
        args["scans"]["/new/state"] = dict(path="/new/state", entries=entries, bytes=12288, inodes=3, device=1, logical_bytes=0)
        args["expected_roots"]["/new/state"] = "state"
        grown = m.quote_bill(**args, sealed=True)
        self.assertEqual(before["proposed_after"]["total"], grown["current"]["total"])
        self.assertNotEqual(before["observations_sha256"], grown["observations_sha256"])
        records = next(row for row in grown["obligations"] if row["id"] == "reconciliation-state")
        self.assertEqual(dict(bytes=8192, inodes=2), records["actual"])
        self.assertEqual(m.BASE_STATE["bytes"] + m.MIB,
            m.startup_costs(grown)["state"]["admitted_bytes"])
        entries[-1]["source_metadata"]["blocks"] = m.MIB // 512
        args["scans"]["/new/state"]["bytes"] = m.MIB + 8192
        with self.assertRaisesRegex(ValueError, "STATE_SUBBUDGET"):
            m.quote_bill(**args, sealed=True)

    def test_seal_is_not_capacity_or_second_execution_authority(self):
        args, _ = fixture(); before = m.quote_bill(**args)
        with self.assertRaisesRegex(ValueError, "MISSING_SEAL"):
            m.startup_costs(before)
        self.assertEqual(132710400, m.startup_costs(before, proposed=True)["installation"]["admitted_bytes"])
        args["devices"][0]["available_bytes"] = 1
        after = m.quote_bill(**args, sealed=True)
        self.assertFalse(after["current"]["admissible"])
        with self.assertRaisesRegex(ValueError, "CAPACITY"):
            m.startup_costs(after)

    def test_inode_capacity_independent_from_bytes(self):
        args, _ = fixture(); args["devices"][0]["free_inodes"] = 1
        quote = m.quote_bill(**args)
        self.assertFalse(quote["proposed_after"]["admissible"])
        self.assertGreater(quote["proposed_after"]["by_device"][1]["available"]["bytes"],
            quote["proposed_after"]["by_device"][1]["future"]["bytes"])

    def test_q1_and_seven_domains_plus_other_hard_limits_are_charged_once(self):
        args, _ = fixture(); before = m.quote_bill(**args)
        self.assertEqual(203 * m.MIB, sum(row["hard_bytes"] for row in before["quota_domains"]))
        self.assertEqual(203 * m.MIB - 11 * 4096, sum(row["unspent"]["bytes"] for row in before["quota_domains"]))
        args["quotas"].append(dict(uuid="synthetic-filesystem", project=99, device=1,
            hard_bytes=9 * m.MIB, hard_inodes=99, used_bytes=m.MIB, used_inodes=1))
        extra = m.quote_bill(**args)
        self.assertEqual(8 * m.MIB, extra["proposed_after"]["future"]["bytes"] - before["proposed_after"]["future"]["bytes"])
        args["quotas"].append(copy.deepcopy(args["quotas"][0]))
        with self.assertRaisesRegex(ValueError, "QUOTA_ALIAS"):
            m.quote_bill(**args)

    def test_shared_pool_future_on_possible_devices_never_duplicates_same_device(self):
        args, _ = fixture()
        args["devices"].append(dict(device=2, available_bytes=2**32, free_inodes=100000))
        owner = next(row for row in args["new_obligations"] if row["id"] == "new-owner-pool")
        owner["devices"] = [1, 2]
        quote = m.quote_bill(**args)
        self.assertEqual(m.OWNER_POOL, quote["proposed_after"]["by_device"][2]["future"])
        owner["devices"] = [1, 1]
        with self.assertRaisesRegex(ValueError, "DEVICE_ALIAS"):
            m.quote_bill(**args)

    def test_unknown_boolean_overflow_alias_and_summary_forgery_rejected(self):
        mutations = (
            lambda a: a["obligations"][0].update(released=True),
            lambda a: a["obligations"][0]["commitment"].update(bytes=True),
            lambda a: a["devices"][0].update(available_bytes=2**63),
            lambda a: a["scans"]["/old/install"]["entries"][0]["source_metadata"].update(blocks=2**62),
            lambda a: a["scans"]["/old/install"].update(bytes=0),
            lambda a: a["obligations"][1].update(covered_paths=["/old/../old/stage"]),
            lambda a: a["new_obligations"][0].update(devices=[True]),
            lambda a: a["scans"]["/old/install"]["entries"][1]["source_metadata"].update(nlink=2),
            lambda a: a["new_obligations"][1].update(excluded_paths=[]),
            lambda a: a["quotas"].pop(),
            lambda a: a["quotas"][0].update(hard_bytes=1),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                args, _ = fixture(); mutation(args)
                with self.assertRaises(ValueError):
                    m.quote_bill(**args)

    def test_logical_sparse_size_does_not_replace_allocated_blocks(self):
        args, _ = fixture()
        entry = args["scans"]["/old/install"]["entries"][1]
        entry["source_metadata"]["size"] = 16 * m.MIB
        args["scans"]["/old/install"]["logical_bytes"] = 16 * m.MIB
        quote = m.quote_bill(**args)
        self.assertEqual(35450880, quote["obligations"][0]["actual"]["bytes"])

    def test_q1_complete_scan_can_enclose_cost_roots_only_with_exact_matching_members(self):
        args, scan = fixture(); before = m.quote_bill(**args)
        scan("/old", "quota", 4096)
        parent = args["scans"]["/old"]
        for root, child in list(args["scans"].items()):
            if root.startswith("/old/"):
                for row in child["entries"]:
                    row = copy.deepcopy(row)
                    row["relative_path"] = root[len("/old/"):] + (
                        "" if row["relative_path"] == "." else "/" + row["relative_path"])
                    parent["entries"].append(row)
                parent["bytes"] += child["bytes"]
                parent["inodes"] += child["inodes"]
        nested = m.quote_bill(**args)
        self.assertEqual(before["actual_count"] + 1, nested["actual_count"])
        self.assertEqual(before["proposed_after"]["categories"], nested["proposed_after"]["categories"])
        parent["entries"][1]["source_metadata"]["atime_ns"] = 2
        with self.assertRaisesRegex(ValueError, "REPEATED_OBSERVATION_CHANGED"):
            m.quote_bill(**args)
        parent["entries"][1]["source_metadata"]["atime_ns"] = 1
        removed = parent["entries"].pop()
        parent["inodes"] -= 1
        parent["bytes"] -= removed["source_metadata"]["blocks"] * 512
        with self.assertRaisesRegex(ValueError, "NESTED_SCAN_COVERAGE"):
            m.quote_bill(**args)

    def test_quota_uuid_cannot_alias_devices(self):
        args, _ = fixture()
        args["devices"].append(dict(device=2, available_bytes=2**32, free_inodes=100000))
        args["quotas"][0]["device"] = 2
        with self.assertRaisesRegex(ValueError, "QUOTA_DEVICE_ALIAS"):
            m.quote_bill(**args)

    def test_real_preflight_project_zero_background_usage_is_preserved(self):
        args, _ = fixture(); before = m.quote_bill(**args)
        background = dict(uuid="synthetic-filesystem", project=0, device=1,
            hard_bytes=0, hard_inodes=0, used_bytes=24576, used_inodes=3)
        args["quotas"].insert(0, background)
        quote = m.quote_bill(**args)
        self.assertEqual(dict(background, unspent=dict(bytes=0, inodes=0)), quote["quota_domains"][0])
        self.assertEqual(before["proposed_after"]["future"], quote["proposed_after"]["future"])
        args["quota_expected"][0]["project"] = 0
        with self.assertRaisesRegex(ValueError, "INTEGER"):
            m.quote_bill(**args)

    def test_total_allocated_scan_bound_is_distinct_from_small_logical_sizes(self):
        args, scan = fixture()
        scan("/uncovered/large", "state", 512 * m.MIB, 1)
        with self.assertRaisesRegex(ValueError, "SCAN_BYTES"):
            m.quote_bill(**args)

    def test_four_original_mount_devices_and_shared_owner_pool(self):
        args, _ = fixture()
        args["devices"] = [dict(device=device, available_bytes=2**32, free_inodes=100000)
            for device in (1, 2, 3, 4)]
        mapping = dict(installation=1, state=1, quota=2, journal=3, capture=4)
        for root, scan in args["scans"].items():
            device = mapping[args["expected_roots"][root]]
            scan["device"] = device
            for entry in scan["entries"]:
                entry["source_metadata"]["device"] = device
        for row in args["quotas"]:
            row["device"] = 2
        next(row for row in args["new_obligations"] if row["id"] == "new-owner-pool")["devices"] = [3, 4]
        quote = m.quote_bill(**args)
        by_device = quote["proposed_after"]["by_device"]
        self.assertEqual({1, 2, 3, 4}, set(by_device))
        self.assertEqual(203 * m.MIB - 11 * 4096, by_device[2]["future"]["bytes"])
        self.assertEqual(by_device[3]["future"], by_device[4]["future"])
        self.assertEqual(2 * (20 * m.MIB - 12288) + 20 * m.MIB, by_device[3]["future"]["bytes"])
        self.assertTrue(quote["proposed_after"]["admissible"])


if __name__ == "__main__":
    unittest.main()
