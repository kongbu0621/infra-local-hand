"""Common-ceiling and physical-device counterexamples for the host window."""
import copy
import importlib.util
import json
from pathlib import Path
import stat
import unittest

from test_e3_q2_reconciliation_billing import fixture as guest_fixture, m as guest_billing

spec = importlib.util.spec_from_file_location("_host_window_bill_tests",
    Path(__file__).parent / "e3_host/q2_host_window_billing.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def scan(root, inode, *, logical=1024, allocated=8192, filename="payload.json"):
    entries = []
    for index in (0, 1):
        meta = dict(device=1, inode=inode + index, st_mode=(stat.S_IFDIR | 0o700) if index == 0 else (stat.S_IFREG | 0o600),
            uid=1000, gid=1000, nlink=1, size=0 if index == 0 else logical,
            blocks=8 if index == 0 else (allocated - 4096) // 512, atime_ns=1, mtime_ns=1, ctime_ns=1)
        entry = dict(relative_path="." if index == 0 else filename,
            type="directory" if index == 0 else "file", source_metadata=meta)
        if index:
            entry["sha256"] = "a" * 64
        entries.append(entry)
    return dict(path=root, entries=entries, bytes=allocated, inodes=2, device=1, logical_bytes=logical)


def fixture():
    root = "/synthetic-host/old-result"
    marker = "/synthetic-host/" + m.MARKER_NAME
    evidence = "a" * 64
    rows = [dict(id="old-host-future", kind="historical", category="capture", commitment=dict(bytes=262144, inodes=8),
        covered_paths=[root], devices=[1], evidence_sha256=evidence),
        dict(id="host-capture", kind="capture", category="capture",
            commitment=m.host_capture_peak(4096, metadata_bound_bytes=8192),
            covered_paths=["/synthetic-host/new-result"], devices=[1], evidence_sha256=evidence),
        dict(id="host-window-marker", kind="marker", category="capture", commitment=dict(m.MARKER_PEAK),
            covered_paths=[marker], devices=[1], evidence_sha256=evidence)]
    return dict(host_id="1" * 64, guest_id="2" * 64, scans={root: scan(root, 100)},
        expected_roots={root: "capture"}, devices=[dict(device=1, available_bytes=128 * 1024**2, free_inodes=10000)],
        obligations=rows, marker=dict(path=marker, device=1, state="ABSENT"),
        early_audit=dict(evidence_sha256=evidence, host_obligation_ids=[], guest_obligation_id="new-owner-pool",
            guest_reserved=dict(bytes=3 * 1024**2, inodes=192)), coverage_sha256="c" * 64)


def consume(inventory):
    value = copy.deepcopy(inventory); root = value["marker"]["path"]
    value["marker"]["state"] = "DURABLE"
    value["scans"][root] = scan(root, 200, filename=m.MARKER_FILE)
    value["expected_roots"][root] = "capture"
    value["devices"][0]["available_bytes"] -= 8192
    value["devices"][0]["free_inodes"] -= 2
    return value


class HostWindowBilling(unittest.TestCase):
    def test_marker_actual_is_covered_once_by_fixed_reservation(self):
        inventory = fixture(); before = m.precheck_costs(inventory)
        consumed = m.quote_host(consume(inventory))
        proof = m.validate_marker_transition(before, consumed)
        self.assertEqual(before["summary"]["total"], consumed["summary"]["total"])
        self.assertEqual(dict(bytes=8192, inodes=2), proof["marker"]["actual"])
        self.assertEqual(m.MARKER_PEAK, proof["marker"]["commitment"])
        self.assertFalse(before["summary"]["joint_admission_proven"])
        self.assertTrue(before["summary"]["local_admissible"])

    def test_joint_capture_uses_one_original_ceiling_and_preserves_other_categories(self):
        args, _ = guest_fixture(); guest = guest_billing.quote_bill(**args)
        host = m.quote_host(consume(fixture()))
        combined = m.joint_quote(guest, host)
        chosen = m.require_joint_admissible(combined, proposed=True)
        self.assertEqual(64 * 1024**2, chosen["categories"]["capture"]["ceiling"]["bytes"])
        self.assertEqual(4096, chosen["categories"]["capture"]["ceiling"]["inodes"])
        self.assertEqual(guest["proposed_after"]["categories"]["installation"], chosen["categories"]["installation"])
        self.assertEqual(guest["proposed_after"]["categories"]["state"], chosen["categories"]["state"])
        self.assertEqual(guest["terminated_unspent"], combined["terminated_unspent"])
        for key in ("bytes", "inodes"):
            self.assertEqual(guest["proposed_after"]["categories"]["capture"]["admitted"][key]
                + host["summary"]["categories"]["capture"]["admitted"][key], chosen["categories"]["capture"]["admitted"][key])
        with self.assertRaisesRegex(ValueError, "GUEST_SEAL_REQUIRED"):
            m.require_joint_admissible(combined)

    def test_realistic_old_host_occupancy_can_block_joint_while_local_host_fits(self):
        inventory = fixture(); root = "/synthetic-host/old-result"
        inventory["scans"][root] = scan(root, 100, logical=13 * 1024**2, allocated=13 * 1024**2)
        precheck = m.precheck_costs(inventory)
        self.assertTrue(precheck["summary"]["local_admissible"])
        args, _ = guest_fixture(); guest = guest_billing.quote_bill(**args)
        joint = m.joint_quote(guest, m.quote_host(consume(inventory)))
        self.assertFalse(joint["proposed_after"]["admissible"])
        with self.assertRaisesRegex(ValueError, "JOINT_CAPACITY"):
            m.require_joint_admissible(joint, proposed=True)
        # No host storage is credited to any historical guest owner pool.
        self.assertEqual(guest["terminated_unspent"], joint["terminated_unspent"])

    def test_same_numeric_device_on_different_machines_never_shares_free_space(self):
        args, _ = guest_fixture(); guest = guest_billing.quote_bill(**args)
        host = m.quote_host(consume(fixture())); combined = m.joint_quote(guest, host)
        devices = combined["proposed_after"]["by_device"]
        self.assertEqual({"1" * 64 + ":1", "2" * 64 + ":1"}, set(devices))
        self.assertEqual(host["summary"]["by_device"]["1"], devices["1" * 64 + ":1"])
        self.assertEqual(guest["proposed_after"]["by_device"][1], devices["2" * 64 + ":1"])

    def test_unknown_obligation_audit_and_allocated_amounts_do_not_default_zero(self):
        mutations = (
            lambda v: v["obligations"][0].update(commitment=None),
            lambda v: v["obligations"][0]["commitment"].update(bytes=0),
            lambda v: v["obligations"][0]["commitment"].update(bytes=True),
            lambda v: v["early_audit"].update(guest_reserved=None),
            lambda v: v["early_audit"]["guest_reserved"].update(bytes=0),
            lambda v: v.update(coverage_sha256=None),
            lambda v: v["scans"]["/synthetic-host/old-result"]["entries"][0]["source_metadata"].pop("blocks"),
            lambda v: v["obligations"][0].update(guest_pool_credit="new-owner-pool"),
        )
        for mutation in mutations:
            value = fixture(); mutation(value)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                m.precheck_costs(value)

    def test_source_proof_and_summaries_cannot_be_replaced_after_precheck(self):
        before = m.precheck_costs(fixture()); changed = copy.deepcopy(before)
        changed["summary"]["actual"]["bytes"] = 0
        with self.assertRaisesRegex(ValueError, "QUOTE_CHANGED"):
            m.validate_host_bill(changed)
        changed = copy.deepcopy(before)
        changed["summary"]["joint_admission_proven"] = 0
        with self.assertRaisesRegex(ValueError, "QUOTE_CHANGED"):
            m.validate_host_bill(changed)
        after = consume(fixture()); after["coverage_sha256"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "MARKER_DECLARATION_DRIFT"):
            m.validate_marker_transition(before, m.quote_host(after))

    def test_consumed_marker_is_required_and_existing_precheck_not_reusable(self):
        before = m.precheck_costs(fixture()); args, _ = guest_fixture()
        with self.assertRaisesRegex(ValueError, "DURABLE_MARKER_REQUIRED"):
            m.joint_quote(guest_billing.quote_bill(**args), before)
        with self.assertRaisesRegex(ValueError, "PRECHECK_ALREADY_CONSUMED"):
            m.precheck_costs(consume(fixture()))

    def test_marker_logical_allocation_and_exact_member_caps(self):
        for change in ("logical", "directory-logical", "allocated", "extra"):
            value = consume(fixture()); root = value["marker"]["path"]
            if change == "logical":
                value["scans"][root] = scan(root, 200, filename=m.MARKER_FILE, logical=16385)
            elif change == "directory-logical":
                value["scans"][root] = scan(root, 200, filename=m.MARKER_FILE, logical=16384)
                value["scans"][root]["entries"][0]["source_metadata"]["size"] = 4096
            elif change == "allocated":
                value["scans"][root] = scan(root, 200, filename=m.MARKER_FILE, allocated=65536 + 512)
            else:
                value["scans"][root] = scan(root, 200, filename="other.json")
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.quote_host(value)

    def test_marker_transition_preserves_old_host_tree_and_cannot_change_location(self):
        before = m.precheck_costs(fixture()); changed = consume(fixture())
        changed["scans"]["/synthetic-host/old-result"]["entries"][1]["sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "HOST_HISTORY_DRIFT"):
            m.validate_marker_transition(before, m.quote_host(changed))
        changed = fixture(); changed["marker"]["path"] = "/synthetic-host/free-choice"
        with self.assertRaisesRegex(ValueError, "MARKER"):
            m.precheck_costs(changed)

    def test_capture_growth_uses_same_peak_and_no_second_full_pool(self):
        value = consume(fixture()); before = m.quote_host(value)
        root = "/synthetic-host/new-result"
        value["scans"][root] = scan(root, 300, logical=2 * 1024**2, allocated=2 * 1024**2 + 4096)
        value["expected_roots"][root] = "capture"
        after = m.quote_host(value)
        self.assertEqual(before["summary"]["total"], after["summary"]["total"])
        value["scans"][root] = scan(root, 300, logical=3 * 1024**2 + 1, allocated=3 * 1024**2 + 4096)
        with self.assertRaisesRegex(ValueError, "NEW_CAPTURE_SUBBUDGET"):
            m.quote_host(value)

    def test_audit_storage_is_counted_once_and_unknown_guest_pool_rejected(self):
        value = consume(fixture())
        value["obligations"].append(dict(id="host-native-audit", kind="audit", category="journal",
            commitment=dict(bytes=4096, inodes=1), covered_paths=["/synthetic-host/owned-audit"], devices=[1], evidence_sha256="a" * 64))
        value["early_audit"]["host_obligation_ids"] = ["host-native-audit"]
        host = m.quote_host(value); args, _ = guest_fixture(); guest = guest_billing.quote_bill(**args)
        combined = m.joint_quote(guest, host)
        self.assertEqual(guest["proposed_after"]["categories"]["journal"]["admitted"]["bytes"] + 4096,
            combined["proposed_after"]["categories"]["journal"]["admitted"]["bytes"])
        # Guest's pre-reserved management portion is included in its owner
        # pool already; the joint bill adds only independent host costs.
        self.assertEqual(guest["proposed_after"]["future"]["bytes"] + host["summary"]["future"]["bytes"],
            combined["proposed_after"]["future"]["bytes"])
        guest["obligations"] = [row for row in guest["obligations"] if row["id"] != "new-owner-pool"]
        with self.assertRaisesRegex(ValueError, "EARLY_GUEST_AUDIT_UNCOVERED"):
            m.joint_quote(guest, host)

    def test_local_bytes_inode_capacity_and_peak_geometry_are_independent(self):
        for key in ("available_bytes", "free_inodes"):
            value = fixture(); value["devices"][0][key] = 1
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "LOCAL_CAPACITY"):
                m.precheck_costs(value)
        self.assertGreater(m.host_capture_peak(65536, metadata_bound_bytes=65536)["bytes"],
            m.host_capture_peak(4096, metadata_bound_bytes=8192)["bytes"])
        for unit, metadata in ((True, 8192), (4096, 0), (3072, 8192), (131072, 131072), (4096, 2**63)):
            with self.subTest(unit=unit, metadata=metadata), self.assertRaises(ValueError):
                m.host_capture_peak(unit, metadata_bound_bytes=metadata)

    def test_host_bill_uses_same_ascii_canonical_encoding_as_protocol(self):
        value = fixture()
        value["obligations"][0]["id"] = "历史义务"
        quote = m.quote_host(value)
        canonical = json.dumps(quote, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
        self.assertEqual(canonical, m.encoded(quote))
        self.assertIn(b"\\u5386", canonical)


if __name__ == "__main__":
    unittest.main()
