"""LOGIC_ONLY private result encoding: no process, systemd, quota or host I/O."""
import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from admin.local_hand_quota_observer import admission as a, experiment_evidence as e
from admin.local_hand_quota_observer import protected_inputs as p, systemd_runtime as r
from admin.local_hand_quota_observer.supervision import Decision
from test_e3_quota_monitor import BOOT, INVOCATION, NOW, binding, encoded, report


RUNTIME_DIGEST = "7" * 64
EXPERIMENT_DIGEST = "8" * 64


def controller():
    return {"unit": "q1-controller.service", "invocation_id": "9" * 32,
            "cgroup": "/admin.slice/q1-controller.service", "cgroup_device": 71,
            "cgroup_inode": 72, "boot_id": BOOT, "pid": 1234, "observed_ns": NOW,
            "stdout_pipe_device": 73, "stdout_pipe_inode": 74,
            "stderr_pipe_device": 73, "stderr_pipe_inode": 75}


def outcome(*, observed=False):
    bound = binding()
    unit = dict.fromkeys(r.SHOW_FIELDS, "")
    unit.update(Id=bound.unit, LoadState="loaded", ActiveState="active", SubState="exited",
                InvocationID=INVOCATION, ControlGroup=bound.cgroup, Job="0", ExecMainCode="1",
                ExecMainStatus="0", Result="success", Slice="synthetic-quota.slice", Type="exec",
                ExitType="cgroup", RemainAfterExit="yes", Restart="no", KillMode="control-group")
    ready = {"schema": "local-hand-quota-worker-ready/v1", "boot_id": BOOT, "unit": bound.unit,
             "invocation_id": INVOCATION, "cgroup": bound.cgroup,
             "manifest_digest": bound.manifest.digest, "runtime_digest": RUNTIME_DIGEST,
             "request_id": bound.request_id}
    native = report(bound.manifest)
    native["calls"][6]["errno"] = 13  # Successful rc may retain original stale errno.
    return r.Outcome(Decision("OBSERVED", "PINNED_FACTS_MATCH", True, True) if observed
                     else Decision("UNKNOWN", "QUERY_EXIT_UNSUCCESSFUL", True),
                     bound, encoded(ready) + encoded(native), b"\xff\x00native stderr\n", INVOCATION,
                     bound.manifest.cgroup_parent, 5, unit_facts=tuple(unit.items()))


def encode(value=None, **changes):
    value = outcome() if value is None else value
    options = {"operation": "run", "source_commit": value.binding.manifest.source_commit,
               "runtime_digest": RUNTIME_DIGEST, "experiment_digest": EXPERIMENT_DIGEST,
               "original_ticket": p.encode_ticket(value.binding), "controller_observation": controller()}
    options.update(changes)
    return e.encode_outcome(value, **options)


class EvidenceTests(unittest.TestCase):
    def test_observed_is_private_nonacceptance_record_with_original_identity_and_bytes(self):
        original = outcome(observed=True)
        raw = encode(original)
        self.assertEqual(raw.count(b"\n"), 1)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertLessEqual(len(raw), e.MAX_EVIDENCE_BYTES)
        value = json.loads(raw)
        self.assertEqual(value["schema"], e.SCHEMA)
        self.assertEqual(value["status"], "OBSERVED")
        self.assertEqual(value["decision"]["reason"], "PINNED_FACTS_MATCH")
        self.assertEqual(value["binding"]["issued_ns"], original.binding.issued_ns)
        self.assertEqual(value["binding"]["deadline_ns"], original.binding.deadline_ns)
        self.assertEqual(value["binding"]["root"]["logical_ref"], original.binding.slot.ref)
        self.assertEqual(value["binding"]["unit"], original.binding.unit)
        ticket = p.encode_ticket(original.binding)
        self.assertEqual(value["original_ticket"], {
            "sha256": hashlib.sha256(ticket.encode("ascii")).hexdigest(), "encoded_bytes": len(ticket)})
        for stream in ("stdout", "stderr"):
            self.assertEqual(base64.b64decode(value["capture"][stream]["data"]), getattr(original, stream))
            self.assertEqual(value["capture"][stream]["bytes"], len(getattr(original, stream)))
        native = json.loads(base64.b64decode(value["capture"]["stdout"]["data"]).split(b"\n")[1])
        self.assertEqual(native["calls"][6]["errno"], 13)
        self.assertEqual(value["unit_facts"], dict(original.unit_facts))
        self.assertEqual(value["controller_observation"], controller())
        self.assertNotIn(original.binding.slot.path.encode(), raw)
        for key in ("admission_proven", "real_e3_accepted", "production_supported", "q1_real_exit_accepted",
                    "evidence_complete"):
            self.assertIs(value[key], False)
        self.assertEqual(value["retention"]["policy"], "PERMANENT_NO_RELEASE_OR_REUSE")
        self.assertEqual(value["retention"]["max_intents"], 32)
        self.assertFalse(value["retention"]["resource_release_authorized"])
        self.assertIn("E3_REAL_INTEGRATION_AND_PRODUCTION_ADMISSION", value["unverified"])

    def test_unknown_keeps_partial_binary_output_and_three_distinct_errors(self):
        original = replace(outcome(), stdout=b'\xff\x00{"errno":13', stderr=b"\xfe",
                           cleanup_reason="CLEANUP_IO_UNCERTAIN", journal_reason="JOURNAL_IO_UNCERTAIN",
                           pending_clients=(77, 78), unit_facts=())
        value = json.loads(encode(original))
        self.assertEqual(value["decision"]["reason"], "QUERY_EXIT_UNSUCCESSFUL")
        self.assertEqual(value["cleanup_reason"], "CLEANUP_IO_UNCERTAIN")
        self.assertEqual(value["journal_reason"], "JOURNAL_IO_UNCERTAIN")
        self.assertEqual(value["pending_clients"], [77, 78])
        self.assertEqual(value["control_calls"], 5)
        self.assertEqual(base64.b64decode(value["capture"]["stdout"]["data"]), original.stdout)
        self.assertEqual(value["capture_completeness"], "NOT_REPRESENTED_BY_OUTCOME")
        self.assertEqual(value["independent_eof_facts"], "NOT_REPRESENTED_BY_OUTCOME")
        self.assertTrue(value["decision"]["query_stopped"])
        self.assertFalse(value["evidence_complete"])

    def test_complete_stdout_and_stopped_do_not_upgrade_unknown(self):
        value = json.loads(encode(outcome()))
        self.assertEqual(value["status"], "UNKNOWN")
        self.assertFalse(value["decision"]["facts_match"])
        self.assertFalse(value["evidence_complete"])

    def test_secondary_entry_error_keeps_original_observed_decision(self):
        original = outcome(observed=True)
        value = json.loads(encode(original, entry_error="JOURNAL_CLOSE_UNCERTAIN"))
        self.assertEqual(value["status"], "UNKNOWN")
        self.assertEqual(value["decision"]["status"], "OBSERVED")
        self.assertEqual(value["entry_error"], "JOURNAL_CLOSE_UNCERTAIN")
        self.assertIsNone(value["cleanup_reason"])
        self.assertIsNone(value["journal_reason"])
        self.assertEqual(base64.b64decode(value["capture"]["stdout"]["data"]), original.stdout)

    def test_recovery_always_unknown_and_rejects_fabricated_observed(self):
        value = json.loads(encode(outcome(), operation="recover_original"))
        self.assertEqual(value["status"], "UNKNOWN")
        self.assertEqual(value["binding"]["deadline_ns"], outcome().binding.deadline_ns)
        for original in (outcome(observed=True), replace(outcome(), decision=Decision("WAITING", "EXIT_UNPROVEN"))):
            with self.subTest(decision=original.decision), self.assertRaisesRegex(a.Rejected, "RECOVERY_STATUS"):
                encode(original, operation="recover_original")

    def test_fabricated_observed_and_changed_identity_are_rejected(self):
        good = outcome(observed=True)
        bad_units = dict(good.unit_facts)
        bad_units["InvocationID"] = "0" * 32
        fake_report = good.stdout.replace(b'"errno":13', b'"errno":9999')
        bad_cases = [replace(good, decision=Decision("OBSERVED", "PINNED_FACTS_MATCH")),
                     replace(good, decision=Decision("OBSERVED", "PINNED_FACTS_MATCH", True, True,
                                                    production_supported=True)),
                     replace(good, stdout=b""), replace(good, stdout=good.stdout[:-1]),
                     replace(good, stdout=fake_report), replace(good, unit_facts=()),
                     replace(good, unit_facts=tuple(bad_units.items())),
                     replace(good, invocation_id=None), replace(good, control_calls=0),
                     replace(good, pending_clients=(77,)),
                     replace(good, cleanup_reason="CLEANUP_IO_UNCERTAIN"),
                     replace(good, journal_reason="JOURNAL_IO_UNCERTAIN")]
        for original in bad_cases:
            with self.subTest(original=original), self.assertRaises(a.Rejected):
                encode(original)
        for changes in ({"source_commit": "0" * 40}, {"runtime_digest": "0" * 64},
                        {"original_ticket": p.encode_ticket(binding(request_id="4" * 32))},
                        {"controller_observation": dict(controller(), boot_id="00000000-0000-0000-0000-000000000000")}):
            with self.subTest(changes=changes), self.assertRaises(a.Rejected):
                encode(good, **changes)

    def test_strict_types_counts_and_lengths(self):
        good = outcome()
        bad_units = tuple((key, "x" * r.CONTROL_BYTES if index == 0 else value)
                          for index, (key, value) in enumerate(good.unit_facts))
        duplicate_units = good.unit_facts[:-1] + (good.unit_facts[0],)
        for changes in ({"stdout": bytearray(b"x")}, {"stderr": "text"},
                        {"stdout": b"x" * (e.MAX_CAPTURE_BYTES + 1)},
                        {"control_calls": True}, {"control_calls": r.MAX_CONTROL_CALLS + 1},
                        {"pending_clients": [77]}, {"pending_clients": (True,)},
                        {"pending_clients": (77, 77)},
                        {"pending_clients": tuple(range(1, r.MAX_CONTROL_CALLS + 3))},
                        {"unit_facts": bad_units}, {"unit_facts": duplicate_units},
                        {"unit_facts": (("unexpected", "x"),)},
                        {"empty_scope": "/wrong.slice"}, {"cleanup_reason": "/private/error"},
                        {"decision": Decision("PASS", "UNSUPPORTED")},
                        {"decision": Decision("UNKNOWN", "UNKNOWN", query_stopped=1)},
                        {"decision": Decision("UNKNOWN", "UNKNOWN", facts_match=True)}):
            with self.subTest(changes=changes), self.assertRaises(a.Rejected):
                encode(replace(good, **changes))
        for changes in ({"operation": "retry"}, {"operation": True}, {"runtime_digest": None},
                        {"experiment_digest": "HEAD"}, {"controller_observation": None},
                        {"controller_observation": dict(controller(), pid=True)},
                        {"controller_observation": dict(controller(), extra=True)},
                        {"controller_observation": dict(controller(), unit="x" * 129 + ".service")},
                        {"controller_observation": dict(controller(), stderr_pipe_inode=74)},
                        {"controller_observation": dict(controller(),
                                                         cgroup="/synthetic-quota.slice/q1-controller.service")},
                        {"entry_error": "os error /secret"}):
            with self.subTest(changes=changes), self.assertRaises(a.Rejected):
                encode(good, **changes)

    def test_capture_maximum_is_preserved_and_total_limit_is_independent(self):
        original = replace(outcome(), stdout=bytes(range(256)) * 128, stderr=b"", unit_facts=())
        raw = encode(original)
        self.assertEqual(base64.b64decode(json.loads(raw)["capture"]["stdout"]["data"]), original.stdout)
        self.assertGreater(len(raw), 32768)  # Private evidence is not the Q2 socket response.
        self.assertLessEqual(len(raw), 128 * 1024)
        units = dict(outcome().unit_facts)
        units["ExecStop"] = "\x00" * 15000
        original = replace(original, unit_facts=tuple(units.items()))
        with self.assertRaisesRegex(a.Rejected, "EVIDENCE_BYTE_LIMIT"):
            encode(original)

    def test_encoder_has_no_runtime_or_host_side_effects(self):
        original = outcome(observed=True)
        with patch.object(r.Q1Controller, "run", side_effect=AssertionError("query")), \
                patch.object(r.Q1Controller, "recover_original", side_effect=AssertionError("recover")), \
                patch("builtins.open", side_effect=AssertionError("filesystem")), \
                patch.object(r.os, "open", side_effect=AssertionError("filesystem")), \
                patch.object(r, "boottime_ns", side_effect=AssertionError("clock")):
            self.assertEqual(encode(original), encode(original))

    def test_failure_status_does_not_claim_no_consumption_or_success(self):
        for entered, status in ((False, "REJECTED"), (True, "UNKNOWN")):
            value = json.loads(e.encode_failure("ENTRY_IO_UNCERTAIN", operation="run", controller_entered=entered))
            self.assertEqual(value["status"], status)
            self.assertEqual(value["failure_code"], "ENTRY_IO_UNCERTAIN")
            self.assertFalse(value["outcome_available"])
            self.assertFalse(value["evidence_complete"])
            self.assertEqual(value["retention"]["intent_consumption"], "NOT_DETERMINED_BY_THIS_RECORD")
        value = json.loads(e.encode_failure("LINUX_REQUIRED", status="UNSUPPORTED"))
        self.assertEqual(value["status"], "UNSUPPORTED")
        value = json.loads(e.encode_failure("ENTRY_IO_UNCERTAIN", controller_entered=True,
                                           entry_error="JOURNAL_CLOSE_UNCERTAIN"))
        self.assertEqual(value["failure_code"], "ENTRY_IO_UNCERTAIN")
        self.assertEqual(value["entry_error"], "JOURNAL_CLOSE_UNCERTAIN")
        for changes in ({"status": "OBSERVED"}, {"status": "UNKNOWN"},
                        {"status": "UNSUPPORTED", "controller_entered": True},
                        {"controller_entered": 1}, {"operation": "retry"},
                        {"source_commit": "HEAD"}, {"original_ticket": "not a ticket"}):
            with self.subTest(changes=changes), self.assertRaises(a.Rejected):
                e.encode_failure("ENTRY_IO_UNCERTAIN", **changes)
        for code in ("OS error /private", "A" * 97, "", 7):
            with self.subTest(code=code), self.assertRaises(a.Rejected):
                e.encode_failure(code)


if __name__ == "__main__":
    unittest.main()
