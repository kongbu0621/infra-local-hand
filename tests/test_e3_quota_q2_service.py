"""Real local journal/fsync/flock/process exit; simulated peer/manager/quota.

No socket, service, quota syscall or host fixture is provisioned by these tests.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from local_hand_jobs import bootstrap_roots, quota_contract as q, quota_grant as g
from q2_fixtures import BOOT, SECOND, capacity, make_grant, peer, query, receipt, fence, encoded
if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer.q2_journal import Journal
    from admin.local_hand_quota_observer.q2_service import Service


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux protected journal/flock")
class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="lhq2-", dir=Path.home())
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.cap = capacity()
        self.first = make_grant()
        self.second = make_grant(number=2, phase="business", issued=5*SECOND,
                                 predecessors=[self.first.request.as_dict()["request_id"]])
        self.grants = [self.first, self.second]
        self.clock = {"boot_id": BOOT, "ns": 2*SECOND}
        self.calls = 0

    def open(self):
        if not hasattr(self, "pin"):
            self.pin = Journal.provision(self.root, self.cap, self.grants)
        journal = Journal(self.root, self.pin, self.cap, self.grants)
        self.addCleanup(journal.close)
        return Service(journal, clock=lambda: dict(self.clock))

    def dispatch(self, grant, deadline, remember):
        self.calls += 1
        start = self.clock["ns"]
        remember(query(grant))
        result = receipt(grant, start=start, finish=start+10)
        self.assertLess(start+10, deadline)
        self.clock["ns"] += 20
        return encoded(result)

    def run_query(self, service, grant=None, **kwargs):
        grant = grant or self.first
        options = {"peer": peer(grant), "expected_peer": peer(grant), "dispatch": self.dispatch}
        options.update(kwargs)
        return service.handle(grant.request.wire, **options)

    def close_first(self, service, outcome):
        self.clock["ns"] = 3*SECOND
        proof = fence(self.first, outcome.receipt)
        service.close_phase(self.first.request, proof)
        return proof

    def test_intent_fsync_precedes_delivery_and_exact_duplicate_reads_result(self):
        service = self.open()
        original = os.fsync
        with mock.patch("admin.local_hand_quota_observer.q2_journal.os.fsync", wraps=original) as sync:
            def dispatch(grant, deadline, remember):
                self.assertGreaterEqual(sync.call_count, 1)
                self.assertIn(b'"kind":"INTENT"', (self.root / (grant.request.as_dict()["request_id"] + ".cell")).read_bytes())
                return self.dispatch(grant, deadline, remember)
            first = self.run_query(service, dispatch=dispatch)
        second = self.run_query(service)
        self.assertEqual(("OBSERVED", True), (first.status, first.delivered))
        self.assertEqual(first.receipt, second.receipt)
        self.assertFalse(second.delivered)
        self.assertEqual(1, self.calls)

    def test_restart_and_lost_reply_never_dispatch_again(self):
        first = self.run_query(self.open())
        second = self.run_query(self.open())
        self.assertEqual(first.receipt, second.receipt)
        self.assertEqual(1, self.calls)

    def test_real_process_death_after_durable_intent_is_unknown_without_replay(self):
        self.open().journal.close()
        pid = os.fork()
        if pid == 0:
            service = self.open()
            service.handle(self.first.request.wire, peer=peer(self.first), expected_peer=peer(self.first),
                dispatch=lambda *args: os._exit(17))
            os._exit(99)
        _, status = os.waitpid(pid, 0)
        self.assertEqual(17, os.waitstatus_to_exitcode(status))
        restored = self.open()
        outcome = self.run_query(restored)
        self.assertEqual(("UNKNOWN", None, False), (outcome.status, outcome.receipt, outcome.delivered))
        self.assertEqual(0, self.calls)

    def test_crash_after_invocation_preserves_only_original_identity(self):
        service = self.open()
        def interrupted(grant, deadline, remember):
            remember(query(grant))
            raise KeyboardInterrupt("lost delivery acknowledgement")
        with self.assertRaises(KeyboardInterrupt):
            self.run_query(service, dispatch=interrupted)
        restored = self.open()
        outcome = self.run_query(restored)
        self.assertEqual("UNKNOWN", outcome.status)
        with restored.journal.locked():
            state = restored.journal.scan()[self.first.request.as_dict()["request_id"]]
        self.assertEqual(query(self.first), state["invocation"])
        self.assertEqual(0, self.calls)

    def test_fsync_error_and_late_fsync_do_not_dispatch(self):
        service = self.open()
        with mock.patch("admin.local_hand_quota_observer.q2_journal.os.fsync", side_effect=OSError("sync acknowledgement lost")):
            with self.assertRaises(OSError):
                self.run_query(service)
        with self.assertRaisesRegex(q.QuotaError, "JOURNAL_UNAVAILABLE"):
            self.run_query(service)
        self.assertEqual("UNKNOWN", self.run_query(self.open()).status)
        self.assertEqual(0, self.calls)

    def test_deadline_elapsed_during_fsync_leaves_consumed_intent(self):
        service = self.open()
        real_sync = os.fsync
        def late(descriptor):
            real_sync(descriptor)
            self.clock["ns"] = 12*SECOND
        with mock.patch("admin.local_hand_quota_observer.q2_journal.os.fsync", side_effect=late):
            with self.assertRaisesRegex(q.QuotaError, "DEADLINE"):
                self.run_query(service)
        self.assertEqual(0, self.calls)
        with service.journal.locked():
            self.assertEqual("INTENT", service.journal.scan()[self.first.request.as_dict()["request_id"]]["status"])

    def test_same_uid_wrong_role_pid_or_start_identity_rejected_before_intent(self):
        service = self.open()
        for key, value in (("unit", "business.service"), ("pid", 999), ("start_ticks", 222),
                           ("invocation_id", "e" * 32), ("uid", 9876)):
            observed = dict(peer(self.first), **{key: value})
            with self.subTest(key=key), self.assertRaises(q.QuotaError):
                self.run_query(service, peer=observed)
        with service.journal.locked():
            self.assertTrue(all(state["status"] == "READY" for state in service.journal.scan().values()))

    def test_same_request_id_different_deadline_epoch_generation_binding_rejected(self):
        service = self.open()
        for key in ("deadline_ns", "epoch", "generation", "manifest_digest", "observation_grant_digest"):
            data = self.first.request.as_dict()
            data[key] = data[key] - 1 if key == "deadline_ns" else "0" * len(data[key])
            with self.subTest(key=key), self.assertRaisesRegex(q.QuotaError, "REQUEST_NOT_ADMITTED"):
                service.handle(encoded(data), peer=peer(self.first), expected_peer=peer(self.first), dispatch=self.dispatch)
        self.assertEqual(0, self.calls)

    def test_unknown_and_success_without_phase_fence_both_block_next_phase(self):
        service = self.open()
        self.run_query(service)
        self.clock["ns"] = 6*SECOND
        with self.assertRaisesRegex(q.QuotaError, "PRIOR_EXIT_UNPROVEN"):
            self.run_query(service, self.second)
        self.assertEqual(1, self.calls)

    def test_complete_phase_allows_business_in_same_permanent_allocation(self):
        service = self.open()
        first = self.run_query(service)
        proof = self.close_first(service, first)
        service.close_phase(self.first.request, proof)
        self.clock["ns"] = 6*SECOND
        second = self.run_query(self.open(), self.second)
        self.assertEqual("OBSERVED", second.status)
        self.assertEqual(2, self.calls)
        self.assertEqual(self.first.as_dict()["allocation"]["allocation_id"], self.second.as_dict()["allocation"]["allocation_id"])

    def test_evidence_may_retain_only_its_explicit_fourth_original_root(self):
        data = make_grant(number=2, phase="evidence", offset=10, issued=5*SECOND,
            predecessors=[self.first.request.as_dict()["request_id"]]).as_dict()
        original = self.first.as_dict()
        kept = dict(original["roots"][0], role="retained_store")
        data["roots"][-1] = kept
        allocation = data["allocation"]
        allocation["paths"].pop(allocation["retained_paths"][0])
        retained_path = original["allocation"]["roots"]["work"]
        allocation["retained_paths"] = [retained_path]
        allocation["paths"][retained_path] = {k: kept[k] for k in ("device", "inode", "uid")}
        allocation["grant_digest"] = bootstrap_roots._digest({k: v for k, v in allocation.items() if k != "grant_digest"})
        self.second = g.decode_grant(encoded(data))
        self.grants[1] = self.second
        service = self.open()
        self.close_first(service, self.run_query(service))
        self.clock["ns"] = 6*SECOND
        outcome = self.run_query(service, self.second)
        self.assertEqual("OBSERVED", outcome.status)
        self.assertEqual(4, len(json.loads(outcome.receipt)["roots"]))

    def test_missing_collector_or_eof_proof_cannot_close_phase(self):
        service = self.open()
        result = self.run_query(service)
        self.clock["ns"] = 3*SECOND
        for stage in ("bootstrap", "helper", "reader", "query", "collector"):
            proof = fence(self.first, result.receipt)
            proof["stages"][stage]["stdout_eof"] = False
            with self.subTest(stage=stage), self.assertRaisesRegex(q.QuotaError, "PHASE_EXIT_UNPROVEN"):
                service.close_phase(self.first.request, proof)

    def test_wrong_original_stage_identity_cannot_close_phase(self):
        service = self.open()
        result = self.run_query(service)
        self.clock["ns"] = 3*SECOND
        for stage in ("bootstrap", "helper", "reader", "query", "collector"):
            proof = fence(self.first, result.receipt)
            proof["stages"][stage]["identity"]["unit"] = "foreign.service"
            with self.subTest(stage=stage), self.assertRaisesRegex(q.QuotaError, "PHASE_STAGE_IDENTITY"):
                service.close_phase(self.first.request, proof)

    def test_second_request_for_same_phase_cannot_purchase_another_query(self):
        self.second = make_grant(number=2, issued=5*SECOND,
            predecessors=[self.first.request.as_dict()["request_id"]])
        self.grants[1] = self.second
        service = self.open()
        self.close_first(service, self.run_query(service))
        self.clock["ns"] = 6*SECOND
        with self.assertRaisesRegex(q.QuotaError, "PHASE_CONSUMED"):
            self.run_query(service, self.second)
        self.assertEqual(1, self.calls)

    def test_unknown_intent_blocks_even_an_unrelated_new_operation(self):
        self.second = make_grant(number=2, operation="separate", offset=10, issued=5*SECOND)
        self.grants[1] = self.second
        service = self.open()
        with self.assertRaises(OSError):
            self.run_query(service, dispatch=mock.Mock(side_effect=OSError("delivery lost")))
        self.clock["ns"] = 6*SECOND
        with self.assertRaisesRegex(q.QuotaError, "PRIOR_EXIT_UNPROVEN"):
            self.run_query(self.open(), self.second)
        self.assertEqual(0, self.calls)

    def test_foreign_operation_cannot_reuse_consumed_slot_or_domain(self):
        self.second = make_grant(number=2, operation="foreign", issued=5*SECOND)
        self.grants[1] = self.second
        service = self.open()
        self.close_first(service, self.run_query(service))
        self.clock["ns"] = 6*SECOND
        with self.assertRaisesRegex(q.QuotaError, "RESOURCE_CONSUMED"):
            self.run_query(service, self.second)

    def test_generation_change_cannot_reuse_original_allocation(self):
        changed = self.second.as_dict()
        changed["request"]["generation"] = "0" * 32
        self.second = g.decode_grant(encoded(changed))
        self.grants[1] = self.second
        service = self.open()
        self.close_first(service, self.run_query(service))
        self.clock["ns"] = 6*SECOND
        with self.assertRaisesRegex(q.QuotaError, "RESOURCE_CONSUMED"):
            self.run_query(service, self.second)

    def test_management_capacity_is_permanent_after_success_and_restart(self):
        self.cap["management"]["storage_bytes"] = 2**20
        self.first = make_grant(declared_capacity=self.cap)
        self.second = make_grant(number=2, phase="business", issued=5*SECOND, declared_capacity=self.cap,
            predecessors=[self.first.request.as_dict()["request_id"]])
        self.grants = [self.first, self.second]
        service = self.open()
        self.close_first(service, self.run_query(service))
        self.clock["ns"] = 6*SECOND
        with self.assertRaisesRegex(q.QuotaError, "MANAGEMENT_EXHAUSTED"):
            self.run_query(self.open(), self.second)
        self.assertEqual(1, self.calls)

    def test_two_instances_cannot_dispatch_concurrently(self):
        first, second = self.open(), self.open()
        def concurrent(grant, deadline, remember):
            with self.assertRaisesRegex(q.QuotaError, "JOURNAL_BUSY"):
                self.run_query(second)
            return self.dispatch(grant, deadline, remember)
        self.run_query(first, dispatch=concurrent)
        self.assertEqual(1, self.calls)

    def test_real_cross_process_lock_denies_second_worker(self):
        service = self.open()
        with service.journal.locked():
            pid = os.fork()
            if pid == 0:
                try:
                    self.open()
                except q.QuotaError as error:
                    os._exit(0 if error.code == "JOURNAL_BUSY" else 2)
                os._exit(3)
            _, status = os.waitpid(pid, 0)
        self.assertEqual(0, os.waitstatus_to_exitcode(status))

    def test_missing_cell_policy_or_lock_is_not_recreated(self):
        service = self.open()
        name = self.first.request.as_dict()["request_id"] + ".cell"
        (self.root / name).unlink()
        with self.assertRaises((q.QuotaError, OSError)):
            self.open()
        self.assertFalse((self.root / name).exists())
        with self.assertRaisesRegex(q.QuotaError, "JOURNAL_FILES"):
            self.run_query(service)
        with self.assertRaisesRegex(q.QuotaError, "JOURNAL_EXISTS"):
            Journal.provision(self.root, self.cap, self.grants)

    def test_torn_record_or_unknown_record_never_recovers_as_ready(self):
        self.open().journal.close()
        cell = self.root / (self.first.request.as_dict()["request_id"] + ".cell")
        with cell.open("ab") as stream:
            stream.write(b'{"kind":"INTENT"')
        with self.assertRaisesRegex(q.QuotaError, "JOURNAL_PARTIAL"):
            self.open()
        self.assertEqual(0, self.calls)

    def test_valid_json_corruption_of_record_is_detected_by_hash_chain(self):
        self.run_query(self.open())
        cell = self.root / (self.first.request.as_dict()["request_id"] + ".cell")
        lines = cell.read_bytes().splitlines()
        last = json.loads(lines[-1])
        last["value"]["received_ns"] += 1
        lines[-1] = q._canonical(last, 65536)
        cell.write_bytes(b"\n".join(lines) + b"\n")
        with self.assertRaisesRegex(q.QuotaError, "JOURNAL_CHECKSUM"):
            self.open()

    def test_expired_success_is_retained_without_returning_live_observed(self):
        service = self.open()
        self.run_query(service)
        self.clock["ns"] = 12*SECOND
        with self.assertRaisesRegex(q.QuotaError, "DEADLINE"):
            self.run_query(self.open())
        self.assertEqual(1, self.calls)

    def test_original_peer_cannot_be_replaced_on_a_duplicate(self):
        service = self.open()
        self.run_query(service)
        changed = dict(peer(self.first), pid=9999, start_ticks=9999)
        with self.assertRaisesRegex(q.QuotaError, "ORIGINAL_PEER_CHANGED"):
            self.run_query(service, peer=changed, expected_peer=changed)
        self.assertEqual(1, self.calls)

    def test_replaced_file_or_directory_identity_is_rejected(self):
        service = self.open()
        path = self.root / "lock"
        path.rename(self.root / "old-lock")
        path.touch(mode=0o600)
        (self.root / "old-lock").unlink()
        with self.assertRaisesRegex(q.QuotaError, "JOURNAL_FILE"):
            self.run_query(service)

    def test_partial_or_foreign_query_receipt_retains_intent_without_result(self):
        service = self.open()
        def wrong(grant, deadline, remember):
            remember(query(grant))
            data = receipt(grant, start=self.clock["ns"], finish=self.clock["ns"])
            data["query"]["cgroup"] = "/foreign.slice/" + grant.request.query_unit
            return encoded(data)
        with self.assertRaisesRegex(q.QuotaError, "QUERY_BINDING"):
            self.run_query(service, dispatch=wrong)
        self.assertEqual("UNKNOWN", self.run_query(self.open()).status)

    def test_wrong_boot_expiry_and_clock_regression_cannot_dispatch(self):
        service = self.open()
        self.clock["boot_id"] = "00000000-0000-0000-0000-000000000000"
        with self.assertRaisesRegex(q.QuotaError, "BOOT_BINDING"):
            self.run_query(service)
        self.clock["boot_id"] = BOOT
        self.clock["ns"] = 20*SECOND
        with self.assertRaisesRegex(q.QuotaError, "DEADLINE"):
            self.run_query(service)
        self.clock["ns"] = 2*SECOND
        with self.assertRaises(q.QuotaError):
            self.run_query(service)
        self.assertEqual(0, self.calls)
