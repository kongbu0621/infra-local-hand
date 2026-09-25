"""Real append-only files/flock with modeled clock, manager and quota facts.

These tests do not execute systemd, quota syscalls or claim a host Q3 result.
"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from local_hand_jobs import quota_contract as q, quota_grant as g
from q2_fixtures import BOOT, SECOND, capacity, make_grant, peer, query, receipt, fence, encoded
from test_e3_quota_q2_closure import complete
if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import q2_journal as j
    from admin.local_hand_quota_observer.q2_service import Service


def next_grant(number, phase, predecessors, *, cap=None, operation="fixture", offset=0):
    value = make_grant(number=number, phase=phase, predecessors=predecessors,
        issued=(4*number-3)*SECOND, declared_capacity=capacity() if cap is None else cap,
        operation=operation, offset=offset).as_dict()
    value["budget"]["reserved_boottime_ns"] = value["management"]["issued_ns"]
    return g.decode_grant(encoded(value))


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux permanent journal/flock")
class ChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lhq2chain-", dir=Path.home())
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cap = capacity()
        self.first = make_grant()
        first_id = self.first.request.as_dict()["request_id"]
        self.second = next_grant(2, "business", [first_id])
        self.third = next_grant(3, "evidence", [first_id, self.second.request.as_dict()["request_id"]], offset=10)
        self.grants = [self.first]
        self.clock = dict(boot_id=BOOT, ns=2*SECOND)
        self.dispatches = 0
        patch = mock.patch("admin.local_hand_quota_observer.q2_service._clock", side_effect=lambda:dict(self.clock))
        patch.start(); self.addCleanup(patch.stop)

    def open(self, *, pin=None, grants=None):
        if not hasattr(self, "pin"):
            self.pin = j.Journal.provision_chain(self.root, self.cap, self.grants)
        journal = j.Journal(self.root, self.pin if pin is None else pin, self.cap,
                            self.grants if grants is None else grants)
        self.addCleanup(journal.close)
        return journal

    def observed(self, journal, grant):
        service = Service(journal, clock=lambda:dict(self.clock), closure_version=2)
        self.clock["ns"] = grant.as_dict()["management"]["issued_ns"] + SECOND
        def dispatch(original, deadline, remember):
            self.dispatches += 1
            remember(query(original))
            start = self.clock["ns"]
            self.clock["ns"] += 20
            return encoded(receipt(original, start=start, finish=start+10))
        result = service.handle(grant.request.wire, peer=peer(grant), expected_peer=peer(grant), dispatch=dispatch)
        return service, result

    def closed(self, journal, grant, *, legacy=False):
        service, result = self.observed(journal, grant)
        at = grant.as_dict()["management"]["issued_ns"] + 2*SECOND
        self.clock["ns"] = at
        proof = fence(grant, result.receipt, closed=at) if legacy else complete(grant,
            at=at, observation=json.loads(result.receipt))[0]
        if legacy: service.closure_version = 1
        service.close_phase(grant.request, proof)

    def extend(self, grant):
        self.clock["ns"] = grant.as_dict()["management"]["issued_ns"] + 100
        pin = j.Journal.extend(self.root, self.pin, self.cap, self.grants, grant)
        self.pin = pin
        self.grants.append(grant)
        return self.open()

    def snapshot(self):
        return {path.name: path.read_bytes() for path in self.root.iterdir()}

    def test_all_three_actual_grants_share_original_lock_capacity_and_budget(self):
        first = self.open()
        initial_pin = copy.deepcopy(self.pin)
        initial_policy = (self.root/"policy").read_bytes()
        self.closed(first, self.first)
        retained_first = (self.root/(self.first.request.as_dict()["request_id"]+".cell")).read_bytes()
        second = self.extend(self.second)
        self.closed(second, self.second)
        third = self.extend(self.third)
        self.closed(third, self.third)
        self.assertEqual(3, self.dispatches)
        for name in ("lock", "policy"):
            self.assertEqual(initial_pin["files"][name], self.pin["files"][name])
        self.assertEqual(initial_pin["directory"], self.pin["directory"])
        self.assertTrue((self.root/"policy").read_bytes().startswith(initial_policy))
        self.assertEqual(retained_first, (self.root/(self.first.request.as_dict()["request_id"]+".cell")).read_bytes())
        # Config canonicalization can change dict iteration order, never phase order.
        reopened = self.open(grants=list(reversed(self.grants)))
        with reopened.locked(): self.assertEqual({"CLOSED"}, {state["status"] for state in reopened.scan().values()})
        registrations = [json.loads(line) for line in (self.root/"policy").read_bytes().splitlines()]
        self.assertEqual("local-hand-quota-journal/v3", registrations[0]["schema"])
        self.assertEqual([0,1,2], [row["index"] for row in registrations[1:]])

    def test_old_config_and_open_instance_cannot_operate_after_extension(self):
        old = self.open(); old_pin = copy.deepcopy(self.pin)
        self.closed(old, self.first)
        self.extend(self.second)
        with self.assertRaisesRegex(q.QuotaError, "JOURNAL_FILES"):
            self.open(pin=old_pin, grants=[self.first])
        with self.assertRaisesRegex(q.QuotaError, "JOURNAL_FILES"):
            with old.locked(): old.scan()
        with self.assertRaises(q.QuotaError): self.open(grants=[self.second])
        with self.assertRaises(q.QuotaError): self.open(pin=old_pin)

    def test_only_first_actual_preflight_can_provision_and_legacy_cannot_extend(self):
        for grants in ([self.second], [self.first, self.second], [self.third]):
            with self.subTest(grants=grants), self.assertRaises(q.QuotaError):
                j.Journal.provision_chain(self.root, self.cap, grants)
            self.assertEqual({}, self.snapshot())
        self.pin = j.Journal.provision(self.root, self.cap, [self.first])
        self.closed(self.open(), self.first)
        before = self.snapshot()
        with self.assertRaisesRegex(q.QuotaError, "CHAIN_JOURNAL_REQUIRED"): self.extend(self.second)
        self.assertEqual(before, self.snapshot())

    def test_ready_unknown_observed_and_legacy_closed_block_new_registration(self):
        for state in ("READY", "INTENT", "OBSERVED", "LEGACY"):
            with self.subTest(state=state), tempfile.TemporaryDirectory(dir=Path.home()) as folder:
                self.root = Path(folder); self.pin = j.Journal.provision_chain(self.root,self.cap,[self.first])
                current = self.open()
                if state == "INTENT":
                    with current.locked(): current.append(self.first.request.as_dict()["request_id"], "INTENT",
                        dict(request_digest=self.first.request.digest, peer=peer(self.first), reserved_ns=2*SECOND))
                if state == "OBSERVED": self.observed(current, self.first)
                if state == "LEGACY": self.closed(current, self.first, legacy=True)
                before = self.snapshot()
                with self.assertRaises(q.QuotaError): self.extend(self.second)
                self.assertEqual(before, self.snapshot())

    def test_changed_operation_phase_prefix_original_budget_and_reservation_rejected(self):
        self.closed(self.open(), self.first)
        candidates = [self.first, self.third,
            next_grant(2,"business",[self.first.request.as_dict()["request_id"]],operation="foreign")]
        for key in ("budget_digest", "started_boottime_ns", "deadline_boottime_ns", "limits", "reserved_boottime_ns"):
            value = self.second.as_dict()
            if key == "budget_digest": value["budget"][key] = "f"*64
            elif key == "limits": value["budget"][key]["cpu_seconds"] += 1
            elif key == "reserved_boottime_ns": value["budget"][key] = 2*SECOND
            else: value["budget"][key] += 1
            candidates.append(g.decode_grant(encoded(value)))
        value = self.second.as_dict(); value["predecessors"] = ["f"*32]
        candidates.append(g.decode_grant(encoded(value)))
        value = self.second.as_dict(); value["request"]["generation"] = "f"*32
        candidates.append(g.decode_grant(encoded(value)))
        before = self.snapshot()
        for candidate in candidates:
            with self.subTest(candidate=candidate.digest), self.assertRaises(q.QuotaError): self.extend(candidate)
            self.assertEqual(before, self.snapshot())

    def test_closed_cost_is_never_refunded_to_next_phase(self):
        self.cap["management"]["storage_bytes"] = 2**20
        self.first = make_grant(declared_capacity=self.cap); self.grants = [self.first]
        self.second = next_grant(2,"business",[self.first.request.as_dict()["request_id"]],cap=self.cap)
        self.closed(self.open(), self.first)
        before = self.snapshot()
        with self.assertRaisesRegex(q.QuotaError,"MANAGEMENT_EXHAUSTED"): self.extend(self.second)
        self.assertEqual(before, self.snapshot())

    def test_fsync_failure_at_each_mutation_retains_files_and_cannot_resume_old_pin(self):
        for failure in (1, 2, 3):
            with self.subTest(fsync=failure), tempfile.TemporaryDirectory(dir=Path.home()) as folder:
                self.root = Path(folder); self.pin = j.Journal.provision_chain(self.root,self.cap,[self.first])
                self.closed(self.open(), self.first)
                original = self.snapshot(); old_pin = copy.deepcopy(self.pin)
                sync = os.fsync; count = 0
                def uncertain(descriptor):
                    nonlocal count
                    count += 1; sync(descriptor)
                    if count == failure: raise OSError("fsync acknowledgement lost")
                with mock.patch.object(j.os,"fsync",side_effect=uncertain), self.assertRaises(OSError): self.extend(self.second)
                self.assertTrue((self.root/(self.second.request.as_dict()["request_id"]+".cell")).exists())
                self.assertEqual(original["lock"], (self.root/"lock").read_bytes())
                self.assertTrue((self.root/"policy").read_bytes().startswith(original["policy"]))
                with self.assertRaises(q.QuotaError): self.open(pin=old_pin,grants=[self.first])
                with self.assertRaises(q.QuotaError): self.extend(self.second)

    def test_partial_policy_write_remains_corrupt_even_with_new_inode_pin(self):
        self.closed(self.open(), self.first)
        real_write = j._write; count = 0
        def torn(descriptor, raw):
            nonlocal count
            count += 1
            if count == 2:
                os.write(descriptor, raw[:len(raw)//2]); os.fsync(descriptor)
                raise OSError("partial registration")
            return real_write(descriptor,raw)
        with mock.patch.object(j,"_write",side_effect=torn), self.assertRaises(OSError): self.extend(self.second)
        pin = copy.deepcopy(self.pin); name = self.second.request.as_dict()["request_id"]+".cell"
        info = (self.root/name).stat(); pin["files"][name] = dict(device=info.st_dev,inode=info.st_ino)
        with self.assertRaisesRegex(q.QuotaError,"JOURNAL_POLICY"): self.open(pin=pin,grants=[self.first,self.second])

    def test_torn_new_cell_cannot_be_completed_or_admitted(self):
        self.closed(self.open(), self.first)
        before = self.snapshot()
        def torn(descriptor, raw):
            os.write(descriptor,raw[:5]); os.fsync(descriptor)
            raise OSError("partial cell")
        with mock.patch.object(j,"_write",side_effect=torn), self.assertRaises(OSError): self.extend(self.second)
        name = self.second.request.as_dict()["request_id"]+".cell"
        self.assertEqual(5,(self.root/name).stat().st_size)
        self.assertEqual(before["policy"],(self.root/"policy").read_bytes())
        with self.assertRaises(q.QuotaError): self.extend(self.second)
        self.assertEqual(5,(self.root/name).stat().st_size)

    def test_registration_hash_prefix_and_prior_grant_bytes_cannot_be_substituted(self):
        self.closed(self.open(),self.first); self.extend(self.second)
        policy = (self.root/"policy").read_bytes()
        rows = policy.splitlines()
        altered = json.loads(rows[-1]); altered["previous_digest"] = "f"*64
        (self.root/"policy").write_bytes(b"\n".join([*rows[:-1],encoded(altered)])+b"\n")
        with self.assertRaisesRegex(q.QuotaError,"JOURNAL_POLICY"): self.open()
        (self.root/"policy").write_bytes(policy)
        value = self.first.as_dict(); value["management"]["stages"]["query"]["output_bytes"] -= 1
        changed = g.decode_grant(encoded(value))
        with self.assertRaisesRegex(q.QuotaError,"JOURNAL_POLICY"): self.open(grants=[changed,self.second])

    def test_clock_expiry_reboot_and_late_fsync_never_return_registered_pin(self):
        self.closed(self.open(), self.first)
        for clock in (dict(boot_id=BOOT,ns=16*SECOND),dict(boot_id="00000000-0000-0000-0000-000000000000",ns=6*SECOND)):
            self.clock.update(clock)
            with self.subTest(clock=clock), self.assertRaises(q.QuotaError):
                j.Journal.extend(self.root,self.pin,self.cap,self.grants,self.second)
        self.clock.update(boot_id=BOOT,ns=6*SECOND)
        sync = os.fsync
        def late(descriptor):
            sync(descriptor); self.clock["ns"] = 16*SECOND
        with mock.patch.object(j.os,"fsync",side_effect=late), self.assertRaisesRegex(q.QuotaError,"DEADLINE"):
            j.Journal.extend(self.root,self.pin,self.cap,self.grants,self.second)
        with self.assertRaises(q.QuotaError): self.open()

    def test_cross_process_competing_extension_cannot_enter_retained_lock(self):
        current = self.open(); self.closed(current,self.first)
        before = self.snapshot()
        self.clock["ns"] = 6*SECOND
        with current.locked():
            pid = os.fork()
            if pid == 0:
                try: j.Journal.extend(self.root,self.pin,self.cap,self.grants,self.second)
                except q.QuotaError as error: os._exit(0 if error.code=="JOURNAL_BUSY" else 2)
                os._exit(3)
            _,status = os.waitpid(pid,0)
        self.assertEqual(0,os.waitstatus_to_exitcode(status))
        self.assertEqual(before,self.snapshot())


if __name__ == "__main__": unittest.main()
