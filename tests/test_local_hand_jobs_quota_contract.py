"""LOGIC_ONLY synthetic Q2 claims; no quota, systemd, or admission proof."""
from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand_jobs import quota_contract as q


def encoded(value):
    return json.dumps(value, separators=(",", ":")).encode()


def request_data(phase="preflight", *, deadline=10_000):
    namespace = "reconcile" if phase == "reconcile" else "job"
    return {"schema": "local-hand-quota-observe/v1", "operation": "observe",
            "request_id": "1" * 32, "authority_digest": "2" * 64,
            "installation_digest": "3" * 64, "manifest_digest": "4" * 64,
            "epoch": "5" * 32, "generation": "6" * 32,
            "boot_id": "11111111-2222-3333-4444-555555555555", "slot_ref": "slot-1",
            "execution_id": namespace + "-operation-1-" + phase, "phase": phase,
            "allocation_digest": "7" * 64, "observation_grant_digest": "8" * 64,
            "deadline_ns": deadline}


def root_facts(*, fourth=False):
    return [{"role": role, "device": 71, "inode": 101 + index, "uid": 1234,
             "gid": 1234, "mode": 0o40700, "filesystem": "ext4",
             "filesystem_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
             "project_id": 1001 + index, "xflags": 512, "hard_bytes": 65536,
             "accounting": True, "enforcement": True, "identity_unchanged": True}
            for index, role in enumerate(q.ROOT_ROLES[:4 if fourth else 3])]


def receipt_data(request, roots, *, start=100, finish=200):
    return {"schema": "local-hand-quota-receipt/v1", "request_digest": request.digest,
            "status": "OBSERVED", "reason": "PINNED_FACTS_MATCH",
            "deadline_ns": request.as_dict()["deadline_ns"], "started_ns": start,
            "finished_ns": finish,
            "query": {"unit": request.query_unit, "invocation_id": "9" * 32,
                      "cgroup": "/synthetic.slice/" + request.query_unit},
            "roots": copy.deepcopy(roots),
            "calls": [{"role": root["role"], "operation": operation, "rc": 0, "errno": 0}
                      for root in roots for operation in q.CALL_OPERATIONS],
            "exit": {**dict.fromkeys(q.EXIT_FLAGS, True), "proof_digest": "a" * 64,
                     "exec_main_code": 1, "exec_main_status": 0, "client_returncode": 0}}


class QuotaContractTests(unittest.TestCase):
    def setUp(self):
        self.request = q.decode_request(encoded(request_data()))
        self.roots = root_facts()
        self.receipt = receipt_data(self.request, self.roots)

    def decode(self, value=None, *, request=None, roots=None, now=300):
        return q.decode_receipt(encoded(self.receipt if value is None else value),
            self.request if request is None else request,
            self.roots if roots is None else roots, now_ns=now)

    def test_canonical_digest_and_immutable_results_without_io(self):
        with mock.patch("builtins.open", side_effect=AssertionError("pure contract")), \
             mock.patch("os.stat", side_effect=AssertionError("pure contract")):
            result = self.decode()
        reordered = dict(reversed(list(request_data().items())))
        self.assertEqual(self.request, q.decode_request(encoded(reordered)))
        self.assertEqual(3 * 65536, result.domain_hard_bytes)
        self.assertEqual("OBSERVED", result.as_dict()["status"])
        self.assertNotIn("admission_proven", result.as_dict())
        changed = result.as_dict()
        changed["roots"][0]["hard_bytes"] = 1024
        self.assertEqual(65536, result.as_dict()["roots"][0]["hard_bytes"])
        with self.assertRaises(FrozenInstanceError):
            self.request.wire = b"{}"

    def test_original_int64_deadline_is_not_rounded_to_javascript_number(self):
        for deadline in (2**53 + 1, q.MAX_INTEGER):
            with self.subTest(deadline):
                self.assertEqual(deadline, q.decode_request(encoded(request_data(deadline=deadline)))
                                 .as_dict()["deadline_ns"])
        for deadline in (True, 0, -1, q.MAX_INTEGER + 1, 1.5, "100"):
            with self.subTest(deadline), self.assertRaises(q.QuotaError):
                q.decode_request(encoded(request_data(deadline=deadline)))

    def test_request_byte_limit_is_on_received_bytes(self):
        wire = self.request.wire
        self.assertEqual(self.request, q.decode_request(wire + b" " * (q.REQUEST_LIMIT - len(wire))))
        with self.assertRaisesRegex(q.QuotaError, "BYTE_LIMIT"):
            q.decode_request(wire + b" " * (q.REQUEST_LIMIT + 1 - len(wire)))
        for raw in (b"", "{}", bytearray(b"{}")):
            with self.subTest(raw=raw), self.assertRaises(q.QuotaError):
                q.decode_request(raw)

    def test_duplicate_extra_deep_non_integer_and_invalid_unicode_fail(self):
        wire = self.request.wire
        cases = [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1.0}',
                 b'{"x":"\\ud800"}', b'{"x":"\xff"}', b'[[[[[0]]]]]',
                 b'{"deadline_ns":' + b"9" * 5000 + b'}', wire + b'{}']
        for field in ("path", "fd", "project_id", "argv", "limit", "quota", "setquota"):
            cases.append(encoded({**request_data(), field: "/untrusted"}))
        for raw in cases:
            with self.subTest(raw=raw[:60]), self.assertRaises(q.QuotaError):
                q.decode_request(raw)

    def test_all_identity_and_phase_changes_break_receipt_binding(self):
        for field in ("request_id", "authority_digest", "installation_digest", "manifest_digest",
                      "epoch", "generation", "allocation_digest", "observation_grant_digest"):
            value = request_data()
            value[field] = "b" * len(value[field])
            with self.subTest(field=field), self.assertRaisesRegex(q.QuotaError, "REQUEST_BINDING"):
                self.decode(request=q.decode_request(encoded(value)))
        changes = ({"slot_ref": "slot-2"}, {"execution_id": "job-operation-2-preflight"},
                   {"boot_id": "22222222-2222-3333-4444-555555555555"}, {"deadline_ns": 9999},
                   {"phase": "business", "execution_id": "job-operation-1-business"})
        for change in changes:
            with self.subTest(change=change), self.assertRaisesRegex(q.QuotaError, "REQUEST_BINDING"):
                self.decode(request=q.decode_request(encoded({**request_data(), **change})))

    def test_execution_id_preserves_full_namespace_record_phase(self):
        for execution, phase in (("f" * 32, "preflight"), ("job-a-business", "preflight"),
                ("job--preflight", "preflight"), ("helper-a-preflight", "preflight"),
                ("job-a-reconcile", "reconcile"), ("reconcile-a-business", "business"),
                ("job-a/-preflight", "preflight"), ("job-" + "a" * 200 + "-evidence", "evidence")):
            with self.subTest(execution=execution), self.assertRaises(q.QuotaError):
                q.decode_request(encoded({**request_data(), "phase": phase, "execution_id": execution}))
        for phase in ("preflight", "business", "reconcile", "evidence"):
            value = request_data(phase)
            self.assertEqual(value["execution_id"], q.decode_request(encoded(value)).as_dict()["execution_id"])

    def test_failure_can_preserve_raw_errno_and_partial_facts(self):
        value = copy.deepcopy(self.receipt)
        value.update(status="UNKNOWN", reason="QUOTA_SYSCALL", roots=[self.roots[0]])
        value["calls"] = value["calls"][:2]
        value["calls"][0]["errno"] = 23  # Successful syscall's saved errno is not normalized.
        value["calls"][1].update(rc=-1, errno=1)
        value["exit"]["stdout_eof"] = False
        value["exit"]["proof_digest"] = None
        result = self.decode(value).as_dict()
        self.assertEqual([23, 1], [call["errno"] for call in result["calls"]])
        self.assertEqual("UNKNOWN", result["status"])
        value.update(status="REJECTED", reason="NOT_STARTED", query=None, roots=[], calls=[],
                     started_ns=None, finished_ns=None)
        value["exit"] = {**dict.fromkeys(q.EXIT_FLAGS, False), "proof_digest": None,
                         "exec_main_code": None, "exec_main_status": None, "client_returncode": None}
        self.assertEqual("REJECTED", self.decode(value).as_dict()["status"])

    def test_every_root_field_is_checked_not_only_work(self):
        changes = {"device": 72, "inode": 999, "uid": 1235, "gid": 1235,
                   "mode": 0o40750, "filesystem": "xfs",
                   "filesystem_uuid": "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee",
                   "project_id": 2222, "xflags": 0, "hard_bytes": 131072,
                   "accounting": False, "enforcement": False, "identity_unchanged": False}
        for role_index in range(3):
            for key, change in changes.items():
                value = copy.deepcopy(self.receipt)
                value["roots"][role_index][key] = change
                with self.subTest(role=role_index, key=key), self.assertRaises(q.QuotaError):
                    self.decode(value)
        for removed in range(3):
            value = copy.deepcopy(self.receipt)
            del value["roots"][removed]
            with self.subTest(removed=removed), self.assertRaises(q.QuotaError):
                self.decode(value)

    def test_fourth_root_only_for_evidence_and_exact_expected_set(self):
        roots = root_facts(fourth=True)
        request = q.decode_request(encoded(request_data("evidence")))
        value = receipt_data(request, roots)
        self.assertEqual(4 * 65536, self.decode(value, request=request, roots=roots).domain_hard_bytes)
        with self.assertRaises(q.QuotaError):
            self.decode(value, request=request)
        value["roots"].pop()
        with self.assertRaises(q.QuotaError):
            self.decode(value, request=request, roots=roots)
        with self.assertRaises(q.QuotaError):
            q.validate_expected_roots(roots, "preflight")

    def test_shared_domain_is_counted_once_and_conflict_is_rejected(self):
        roots = root_facts()
        roots[1]["project_id"] = roots[0]["project_id"]
        self.assertEqual(2 * 65536, self.decode(receipt_data(self.request, roots), roots=roots).domain_hard_bytes)
        roots[1]["hard_bytes"] *= 2
        with self.assertRaisesRegex(q.QuotaError, "DOMAIN_LIMIT_CONFLICT"):
            q.validate_expected_roots(roots, "preflight")

    def test_aliases_nonordinary_owners_and_overflow_fail_even_in_expected_roots(self):
        mutations = ((1, "inode", 101), (1, "role", "work"), (1, "device", 72),
                     (1, "filesystem_uuid", "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"),
                     (0, "uid", 0), (0, "uid", True), (0, "uid", 2**32 - 1),
                     (0, "project_id", 0), (0, "xflags", 0), (0, "hard_bytes", 65537),
                     (0, "mode", 0o100700), (0, "accounting", 1))
        for index, key, change in mutations:
            roots = root_facts()
            roots[index][key] = change
            with self.subTest(key=key, change=change), self.assertRaises(q.QuotaError):
                q.validate_expected_roots(roots, "preflight")
        roots = root_facts()
        for root in roots:
            root["hard_bytes"] = 2**62
        with self.assertRaisesRegex(q.QuotaError, "INTEGER"):
            q.validate_expected_roots(roots, "preflight")

    def test_call_order_count_and_stop_at_first_failure(self):
        mutations = [lambda c: c.pop(), lambda c: c.reverse(), lambda c: c.append(c[0]),
                     lambda c: c[0].update(role="retained_store"),
                     lambda c: c[1].update(operation="STATE_BEFORE"),
                     lambda c: c[0].update(rc=-1, errno=1),
                     lambda c: c[0].update(rc=True), lambda c: c[0].update(errno=4096)]
        for index, mutate in enumerate(mutations):
            value = copy.deepcopy(self.receipt)
            mutate(value["calls"])
            with self.subTest(index=index), self.assertRaises(q.QuotaError):
                self.decode(value)
        value = copy.deepcopy(self.receipt)
        value["calls"][0]["errno"] = 122
        self.assertEqual(122, self.decode(value).as_dict()["calls"][0]["errno"])

    def test_every_exit_fact_and_query_identity_is_required_for_observed(self):
        for flag in q.EXIT_FLAGS:
            for change in (False, 1, None):
                value = copy.deepcopy(self.receipt)
                value["exit"][flag] = change
                with self.subTest(flag=flag, change=change), self.assertRaises(q.QuotaError):
                    self.decode(value)
        for key, change in (("proof_digest", None), ("exec_main_code", 2),
                ("exec_main_status", 203), ("client_returncode", -9), ("client_returncode", True)):
            value = copy.deepcopy(self.receipt)
            value["exit"][key] = change
            with self.subTest(key=key), self.assertRaises(q.QuotaError):
                self.decode(value)
        for query in (None, {**self.receipt["query"], "unit": "other.service"},
                      {**self.receipt["query"], "cgroup": "/other.service"},
                      {**self.receipt["query"], "cgroup": "/a/../" + self.request.query_unit},
                      {**self.receipt["query"], "invocation_id": "INVALID"}):
            with self.subTest(query=query), self.assertRaises(q.QuotaError):
                self.decode({**self.receipt, "query": query})

    def test_deadline_cannot_extend_or_accept_future_stale_or_inverted_facts(self):
        self.assertEqual(400, self.decode({**self.receipt, "deadline_ns": 400}).as_dict()["deadline_ns"])
        for changes in ({"deadline_ns": 10001}, {"deadline_ns": 300},
                        {"started_ns": 201}, {"finished_ns": 301}, {"started_ns": None},
                        {"finished_ns": None}, {"started_ns": True}, {"finished_ns": -1}):
            with self.subTest(changes=changes), self.assertRaises(q.QuotaError):
                self.decode({**self.receipt, **changes})

    def test_response_bytes_depth_duplicate_extra_and_partial_frames_are_strict(self):
        wire = encoded(self.receipt)
        padded = wire + b" " * (q.RESPONSE_LIMIT - len(wire))
        self.assertEqual("OBSERVED", q.decode_receipt(padded, self.request, self.roots, now_ns=300)
                         .as_dict()["status"])
        for raw in (padded + b" ", b'[[[[[[[0]]]]]]]', b'{"query":1,"query":2}', wire[:-1],
                    encoded({**self.receipt, "path": "/untrusted"})):
            with self.subTest(raw=raw[:60]), self.assertRaises(q.QuotaError):
                q.decode_receipt(raw, self.request, self.roots, now_ns=300)


if __name__ == "__main__":
    unittest.main()
