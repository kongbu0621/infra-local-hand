"""Canonical bounded Q2 transport; these tests confer no runtime authority."""
import base64
import copy
import json
import random
import struct
import unittest
import zlib

from local_hand_jobs import bootstrap, quota_payload as codec
from local_hand_jobs.contract import JobError


def envelope(raw, *, prefix=codec.BOOTSTRAP_PREFIX, level=9):
    return prefix + base64.b64encode(zlib.compress(raw, level)).decode("ascii")


def payload():
    limits = {"temporary_bytes": 1024**2, "reservation_bytes": 4 * 1024**2}
    events = [{"seq": 1, "kind": "OBSERVED", "observed_at": 12345.123456789,
               "data_json": '{"historical":"unchanged"}'}]
    execution = {"phase": "evidence", "budgets": limits,
        "budget_grant": {"limits": copy.deepcopy(limits)},
        "evidence_snapshot": {"root": "/synthetic/evidence", "broker_events": events},
        "broker_events": copy.deepcopy(events)}
    return {"version": 2, "execution": execution, "allocation": {},
        "observation": {"roots": [{"role": "evidence", "hard_bytes": 1024**2}]}}


class QuotaPayloadTests(unittest.TestCase):
    def test_existing_small_quota_payload_keeps_exact_legacy_bytes(self):
        value = {"version": 2, "execution": {"phase": "preflight"},
                 "allocation": {}, "observation": {}}
        encoded = codec.encode_bootstrap(value)
        self.assertEqual(bootstrap.encode_payload(value), encoded)
        self.assertEqual(value, bootstrap.decode_payload(encoded))
        with self.assertRaises(JobError):
            bootstrap.decode_payload(envelope(codec._raw(value)))

    def test_exact_finite_historical_timestamps_survive_both_boundaries(self):
        value = payload()
        raw = codec._raw(value)
        encoded = codec.encode_bootstrap(value)
        self.assertTrue(encoded.startswith(codec.BOOTSTRAP_PREFIX))
        decoded = bootstrap.decode_payload(encoded)
        self.assertEqual(raw, codec._raw(decoded))
        before = value["execution"]["broker_events"][0]["observed_at"]
        after = decoded["execution"]["broker_events"][0]["observed_at"]
        self.assertEqual(struct.pack("!d", before), struct.pack("!d", after))
        plan = {"phase": "evidence", "evidence_snapshot": value["execution"]["evidence_snapshot"]}
        declaration = codec.encode_phase_plan(plan)
        self.assertEqual({"schema", "encoded_plan"}, set(declaration))
        self.assertEqual(plan, codec.decode_phase_plan(declaration))
        with self.assertRaises(JobError):
            bootstrap.encode_payload(value)  # Legacy float policy is unchanged.

    def test_large_evidence_payload_has_finite_single_argument(self):
        value = payload()
        value["execution"]["broker_events"][0]["data_json"] = "x" * 150000
        encoded = codec.encode_bootstrap(value)
        self.assertGreater(len(codec._raw(value)), bootstrap.MAX_PAYLOAD_BYTES)
        self.assertLess(len(encoded), codec.MAX_ENCODED_BYTES)
        self.assertEqual(value, bootstrap.decode_payload(encoded))
        bootstrap.check_argv(["/usr/bin/python3", "-I", "/synthetic/runner.py", "--bootstrap", encoded], {})

    def test_artifact_cannot_exceed_any_original_write_bound(self):
        for field in ("temporary_bytes", "reservation_bytes", "hard_bytes", "changed_limits"):
            value = payload()
            if field == "hard_bytes":
                value["observation"]["roots"][0][field] = 1
            elif field == "changed_limits":
                value["execution"]["budgets"] = {"temporary_bytes": 1}
            else:
                value["execution"]["budgets"][field] = 1
                value["execution"]["budget_grant"]["limits"][field] = 1
            with self.subTest(field=field), self.assertRaises(JobError):
                codec.encode_bootstrap(value)
            with self.subTest(field=field), self.assertRaises(JobError):
                bootstrap.decode_payload(envelope(codec._raw(value)))

    def test_receipt_marker_and_directory_are_debited_before_launch(self):
        value = payload()
        value["observation"]["roots"][0]["hard_bytes"] = 65536
        execution = value["execution"]
        execution["broker_events"][0]["data_json"] = ""
        execution["broker_events"][0]["data_json"] = "x" * (65535 - len(codec._raw(execution)))
        self.assertEqual(65535, len(codec._raw(execution)))
        with self.assertRaisesRegex(JobError, "original artifact budget"):
            codec.encode_bootstrap(value)
        observation = {"receipt": "x" * 3000}
        with self.assertRaisesRegex(JobError, "original artifact budget"):
            codec.check_final_artifact(value, observation, b"owner-marker", block_size=4096)

    def test_pending_ordinary_proof_preserves_only_exact_elapsed_measurements(self):
        proof = {"state": "EXITED", "result": {"stages": [{"name": "interpreter",
            "elapsed_seconds": 0.0123456789, "exit_code": 0}]}}
        snapshot = {"preparation": {}, "observation": None, "closed": None,
                    "pending": {"phase": "preflight", "proof": proof}}
        from local_hand_jobs import quota_closure
        copied = codec.decode_bridge_value(codec.encode_bridge_value(snapshot))
        self.assertEqual(snapshot, copied)
        self.assertEqual(quota_closure.digest(proof), quota_closure.digest(copied["pending"]["proof"]))
        for changed in (-0.1, float("inf"), float("nan")):
            bad = copy.deepcopy(snapshot)
            bad["pending"]["proof"]["result"]["stages"][0]["elapsed_seconds"] = changed
            with self.subTest(changed=changed), self.assertRaises(JobError):
                codec.encode_bridge_value(bad)
        for field in ("deadline_ns", "observed_ns", "hard_bytes"):
            bad = copy.deepcopy(snapshot)
            bad["pending"]["proof"][field] = 1.5
            with self.subTest(field=field), self.assertRaises(JobError):
                codec.encode_bridge_value(bad)
        wrong = codec.encode_bridge_value(snapshot)
        wrong["pending"]["proof"]["schema"] = codec.PLAN_SCHEMA
        with self.assertRaises(JobError):
            codec.decode_bridge_value(wrong)

    def test_float_exception_never_changes_quota_or_other_field_policy(self):
        for fault in ("budget", "quota", "elsewhere", "not_finite", "secret", "phase"):
            value = payload()
            if fault == "budget":
                value["execution"]["budgets"]["temporary_bytes"] = 1.0
            elif fault == "quota":
                value["observation"]["roots"][0]["hard_bytes"] = 1.0
            elif fault == "elsewhere":
                value["execution"]["evidence_snapshot"]["observed_at"] = 1.5
            elif fault == "not_finite":
                value["execution"]["broker_events"][0]["observed_at"] = float("inf")
            elif fault == "secret":
                value["execution"]["broker_events"][0]["password"] = "not-transported"
            else:
                value["execution"]["phase"] = "preflight"
            with self.subTest(fault=fault), self.assertRaises(JobError):
                codec.encode_bootstrap(value)

    def test_bombs_extra_streams_and_noncanonical_json_fail_closed(self):
        raw = codec._raw(payload())
        data = zlib.compress(raw, 9)
        damaged = [
            envelope(b'{"value":"' + b"x" * codec.MAX_DECODED_BYTES + b'"}'),
            codec.BOOTSTRAP_PREFIX + base64.b64encode(data + b"trailing").decode(),
            codec.BOOTSTRAP_PREFIX + base64.b64encode(data + data).decode(),
            codec.BOOTSTRAP_PREFIX + base64.b64encode(data[:-1]).decode(),
            envelope(raw, level=0),
            envelope(raw + b"\n"),
            envelope(b'{"version":2,"version":2}'),
            envelope(b'{"value":NaN}'),
            envelope(b'{"value":1e999}'),
            codec.BOOTSTRAP_PREFIX + "not-base64",
            codec.BOOTSTRAP_PREFIX + "x" * codec.MAX_ENCODED_BYTES,
        ]
        for index, encoded in enumerate(damaged):
            with self.subTest(index=index), self.assertRaises(JobError):
                bootstrap.decode_payload(encoded)

    def test_fixed_decoded_and_encoded_bounds_are_independent(self):
        value = payload()
        value["execution"]["broker_events"][0]["data_json"] = "x" * codec.MAX_DECODED_BYTES
        with self.assertRaises(JobError):
            codec.encode_bootstrap(value)
        value = payload()
        rng = random.Random(901)
        value["execution"]["broker_events"][0]["data_json"] = rng.randbytes(100000).hex()
        self.assertLess(len(codec._raw(value)), codec.MAX_DECODED_BYTES)
        with self.assertRaises(JobError):
            codec.encode_bootstrap(value)

    def test_phase_declaration_requires_exact_version_shape_and_prefix(self):
        valid = codec.encode_phase_plan({"phase": "preflight"})
        for value in (dict(valid, argv=[]), dict(valid, schema="local-hand-q2-phase-plan/v1"),
                      dict(valid, encoded_plan=codec.encode_bootstrap(payload())),
                      dict(valid, encoded_plan=valid["encoded_plan"] + "\n")):
            with self.subTest(value=list(value)), self.assertRaises(JobError):
                codec.decode_phase_plan(value)


if __name__ == "__main__":
    unittest.main()
