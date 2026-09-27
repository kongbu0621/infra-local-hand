"""CPUQuota wire admission and legacy evidence, with an independent parser.

The native check calls only systemd's pure percentage parser through ctypes.
No test launches a service, connects to a manager, or changes a cgroup.
"""
import copy
import ctypes
import errno
from fractions import Fraction
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest("Linux CPUQuota runtime imports and native systemd parser")

from admin.local_hand_quota_observer import controller_guard as guard
from local_hand_jobs import runner
from test_e3_quota_controller_guard import controller_value
from test_e3_quota_launcher import fixture as launch_fixture, decode as decode_launch
from test_e3_quota_q2_prepare import m as prepare
from test_e3_quota_q2_prepare_contract import m as contract, fixture as prepare_fixture, decode as decode_prepare
from test_e3_quota_q2_prepare_driver import d as driver, fixture as driver_fixture
from test_e3_quota_q2_supervisor import s as supervisor, launcher, fixture as supervisor_fixture, BOOT, SECOND
from test_e3_quota_q2_evidence_review import r as review
import test_e3_quota_q2_evidence_review as retained_review


EXACT = ((1000, "0.1%"), (1100, "0.11%"), (10000, "1%"),
         (250100, "25.01%"), (333300, "33.33%"),
         (999900, "99.99%"), (1000000, "100%"))
FORMAT = "systemd-percent-hundredths/v1"


def controller_command(value):
    binding = supervisor.validate(value, launcher, dict(boot_id=BOOT, boottime_ns=2 * SECOND))
    repository = Path(value["launcher"]["resident"]["entry"]["path"]).parents[2]
    return supervisor.command(value, binding, repository,
        value["declarations"]["path"] + "/supervisor.json", "a" * 64)


class DeclaredQuotaTests(unittest.TestCase):
    def test_exact_rate_has_the_same_wire_value_in_controller_and_preparation(self):
        for rate, expected in EXACT:
            with self.subTest(rate=rate):
                self.assertEqual(expected, guard.cpu_quota_percent(rate))
                self.assertEqual(expected, contract.cpu_quota_percent(rate))
                self.assertEqual(Fraction(rate, 1000000), Fraction(expected[:-1]) / 100)
                value = dict(controller_value(), cpu_quota_per_sec_usec=rate)
                self.assertEqual(rate, guard.decode_controller(value).cpu_quota_per_sec_usec)
                parent = dict(cpu_quota_per_sec_usec=rate, memory_bytes=67108864, tasks_max=32)
                self.assertIn("\nCPUQuota=" + expected + "\n", prepare.LinuxBackend.slice_bytes(parent).decode())

    def test_controller_and_static_launch_reject_unrepresentable_precision(self):
        for rate in (1001, 250010, 333333, 999999):
            with self.subTest(rate=rate):
                with self.assertRaisesRegex(guard.Rejected, "CONTROLLER_CPU_QUOTA_PRECISION"):
                    guard.decode_controller(dict(controller_value(), cpu_quota_per_sec_usec=rate))
                value = launch_fixture()[3]
                value["controller"]["cpu_quota_per_sec_usec"] = rate
                with self.assertRaisesRegex(guard.Rejected, "CONTROLLER_CPU_QUOTA_PRECISION"):
                    decode_launch(value)

    def test_preparation_rejects_parent_precision_before_backend_construction(self):
        for role in (*contract.SYSTEM_PARENTS, "ordinary"):
            value = prepare_fixture()
            value["parents"][role]["cpu_quota_per_sec_usec"] = 250010
            with self.subTest(role=role), mock.patch.object(prepare, "LinuxBackend") as backend:
                with self.assertRaisesRegex(ValueError, "PREPARE_CPU_QUOTA_PRECISION"):
                    prepare.prepare(value, validate_settings=lambda unused: None)
                backend.assert_not_called()

    def test_preparation_rejects_controller_precision_before_backend_construction(self):
        for role in ("target", "supervisor"):
            value = prepare_fixture()
            value["settings"] = copy.deepcopy(driver_fixture()[0]["settings"])
            value["settings"]["controllers"][role]["cpu_quota_per_sec_usec"] = 333333
            with self.subTest(role=role), mock.patch.object(prepare, "LinuxBackend") as backend:
                with self.assertRaisesRegex(ValueError, "PREPARE_CPU_QUOTA_PRECISION"):
                    prepare.prepare(value, validate_settings=driver.validate_settings)
                backend.assert_not_called()

    def test_representable_parent_and_controller_rates_survive_admission(self):
        for rate in (10000, 250100, 999900, 1000000):
            with self.subTest(rate=rate):
                value = prepare_fixture()
                for parent in value["parents"].values(): parent["cpu_quota_per_sec_usec"] = rate
                self.assertEqual(value, decode_prepare(value))
                settings = driver_fixture()[0]["settings"]
                for control in settings["controllers"].values(): control["cpu_quota_per_sec_usec"] = rate
                driver.validate_settings(settings)


class DeliveryHistoryTests(unittest.TestCase):
    def test_current_command_and_explicit_review_match_without_rewriting_legacy(self):
        for rate, expected in ((250100, "25.01%"), (1000000, "100%")):
            with self.subTest(rate=rate):
                value = supervisor_fixture()
                value["launcher"]["controller_envelope"]["controller"]["cpu_quota_per_sec_usec"] = rate
                command = controller_command(value)
                self.assertIn("--property=CPUQuota=" + expected, command)
                current = review.digest(review.encoded(command))
                self.assertEqual(current, review.delivery_digest(value, "a" * 64, cpu_quota_format=FORMAT))
                legacy_text = "25.0100%" if rate == 250100 else "100.0000%"
                legacy_command = ["--property=CPUQuota=" + legacy_text
                    if arg.startswith("--property=CPUQuota=") else arg for arg in command]
                legacy = review.digest(review.encoded(legacy_command))
                self.assertEqual(legacy, review.delivery_digest(value, "a" * 64))
                self.assertNotEqual(legacy, current)

    def test_unknown_format_and_unrepresentable_new_rate_fail_closed(self):
        value = supervisor_fixture()
        for unknown in ("systemd-percent-hundredths/v2", "", False):
            with self.subTest(unknown=unknown), self.assertRaisesRegex(ValueError, "REVIEW_CPU_QUOTA_FORMAT"):
                review.delivery_digest(value, "a" * 64, cpu_quota_format=unknown)
        value["launcher"]["controller_envelope"]["controller"]["cpu_quota_per_sec_usec"] = 333333
        with self.assertRaisesRegex(ValueError, "REVIEW_CPU_QUOTA_PRECISION"):
            review.delivery_digest(value, "a" * 64, cpu_quota_format=FORMAT)
        # Retained v1 bytes remain reproducible even when the historical input
        # could not be expressed by systemd; digest reconstruction grants no PASS.
        self.assertRegex(review.delivery_digest(value, "a" * 64), r"^[0-9a-f]{64}$")


class SealedDeliveryEncodingTests(unittest.TestCase):
    """Mutate and reseal actual producer bundles, then run the full reviewer.

    Host/manager facts in the reused fixture are modeled. Its files, child exit,
    pipe EOF and hashes are real; an offline pass remains strictly scoped.
    """
    chain = False

    @classmethod
    def setUpClass(cls):
        retained_review.RetainedReviewTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        retained_review.RetainedReviewTests.tearDownClass.__func__(cls)

    setUp = retained_review.RetainedReviewTests.setUp
    rewrite = retained_review.RetainedReviewTests.rewrite
    reseal = retained_review.RetainedReviewTests.reseal

    def check(self):
        return review.review(str(self.root / "output"), str(self.root / "declarations"), self.expected)

    def reject_at_facts(self, reason):
        with mock.patch.object(review, "facts", wraps=review.facts) as facts:
            with self.assertRaisesRegex(ValueError, reason): self.check()
            facts.assert_called_once()

    def make_legacy(self):
        fixture = json.loads((self.root / "declarations/supervisor.json").read_bytes())
        fixture_sha = review.digest((self.root / "declarations/supervisor.json").read_bytes())
        def old_delivery(value):
            value.pop("cpu_quota_format")
            value["argv_sha256"] = review.delivery_digest(fixture, fixture_sha)
        self.rewrite("delivery.json", old_delivery)
        self.reseal()

    def test_new_and_legacy_encoding_each_keep_their_original_offline_contract(self):
        delivery = json.loads((self.root / "output/delivery.json").read_bytes())
        self.assertEqual(FORMAT, delivery["cpu_quota_format"])
        self.assertEqual("OFFLINE_ARTIFACTS_CONSISTENT", self.check()["status"])
        self.make_legacy()
        result = self.check()
        self.assertEqual("OFFLINE_ARTIFACTS_CONSISTENT", result["status"])
        self.assertFalse(result["q3_accepted"])
        self.assertFalse(result["production_supported"])
        self.assertFalse(result["host_provenance_proven"])

    def test_new_command_cannot_be_relabelled_as_legacy_by_deleting_marker(self):
        self.rewrite("delivery.json", lambda value: value.pop("cpu_quota_format"))
        self.reseal()
        self.reject_at_facts("REVIEW_DELIVERY_BINDING")

    def test_null_unknown_or_explicit_legacy_marker_is_not_implicit_legacy(self):
        original = (self.root / "output/delivery.json").read_bytes()
        for marker in (None, "systemd-percent-hundredths/v2", "legacy-four-places/v1"):
            with self.subTest(marker=marker):
                (self.root / "output/delivery.json").write_bytes(original)
                self.rewrite("delivery.json", lambda value: value.update(cpu_quota_format=marker))
                self.reseal()
                self.reject_at_facts("REVIEW_CPU_QUOTA_FORMAT")

    def test_legacy_command_cannot_be_relabelled_as_new(self):
        self.make_legacy()
        self.rewrite("delivery.json", lambda value: value.update(cpu_quota_format=FORMAT))
        self.reseal()
        self.reject_at_facts("REVIEW_DELIVERY_BINDING")

    def test_resealed_new_declaration_rejects_unrepresentable_cpu_rate(self):
        # Rebind every earlier fixture/hash/cost dependency so the full reviewer
        # reaches the new wire precision check, not an unrelated stale hash.
        fixture_path = self.root / "declarations/supervisor.json"
        fixture = json.loads(fixture_path.read_bytes())
        static = fixture["launcher"]["controller_envelope"]["controller"]
        self.assertEqual((1000000, 90000000, 1000000),
            (static["cpu_quota_per_sec_usec"], static["runtime_max_usec"], static["timeout_stop_usec"]))
        static["cpu_quota_per_sec_usec"] = 999999
        raw = review.encoded(fixture); fixture_path.write_bytes(raw)
        fixture_sha = review.digest(raw)
        self.rewrite("launcher.json", lambda value:
            value["controller_envelope"]["controller"].update(cpu_quota_per_sec_usec=999999), "declarations")
        def reservation(value):
            value["fixture_sha256"] = fixture_sha
            value["target_static"] = fixture["launcher"]["controller_envelope"]
            # 92 s reserved CPU envelope, reduced by exactly 1 microsecond/s.
            value["capacity_costs"]["cpu_ns"] -= 92000
        self.rewrite("reservation.json", reservation)
        for directory in ("output", "declarations"):
            self.rewrite("controller-result.json", lambda value: value.update(fixture_sha256=fixture_sha), directory)
        self.rewrite("seal.json", lambda value: value.update(fixture_sha256=fixture_sha))
        self.reseal()
        self.reject_at_facts("REVIEW_CPU_QUOTA_PRECISION")


class NativeSystemdParserTests(unittest.TestCase):
    def test_systemd_255_parser_accepts_produced_values_and_rejects_old_precision(self):
        candidates = sorted({path for base in (Path("/usr/lib"), Path("/lib"))
            for pattern in ("systemd/libsystemd-shared-255.so", "*/systemd/libsystemd-shared-255.so")
            for path in base.glob(pattern)})
        if not candidates:
            self.skipTest("systemd 255 shared library unavailable; pure serialization tests still apply")
        library = None
        for path in candidates:
            try:
                library = ctypes.CDLL(str(path))
                parse = library.parse_permyriad_unbounded
                break
            except (OSError, AttributeError):
                library = None
        if library is None:
            self.skipTest("systemd 255 pure percentage parser is not loadable")
        parse.argtypes = [ctypes.c_char_p]
        parse.restype = ctypes.c_int
        for wire in (b"100.0000%", b"25.001%", b"0.100000%", b"100.%"):
            with self.subTest(rejected=wire): self.assertEqual(-errno.EINVAL, parse(wire))
        for rate, _ in EXACT:
            for encoder in (guard.cpu_quota_percent, contract.cpu_quota_percent):
                wire = encoder(rate)
                with self.subTest(rate=rate, encoder=encoder.__module__):
                    self.assertEqual(rate, parse(wire.encode("ascii")) * 100)
        for cpu, wall in ((1, 3), (1, 1000), (1, 909), (99999, 100000), (100, 3)):
            wire = runner._cpu_quota(dict(cpu_seconds=cpu, wall_seconds=wall))
            with self.subTest(cpu=cpu, wall=wall):
                native = parse(wire.encode("ascii"))
                self.assertGreaterEqual(native, 10)
                self.assertLessEqual(native * wall, cpu * 10000)
