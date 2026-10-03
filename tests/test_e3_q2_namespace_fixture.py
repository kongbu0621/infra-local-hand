"""Pure F0--F4 contract tests for the Q2 namespace fixture.

Nothing in this file contacts the guest, creates a process, or writes cgroupfs.
The final native test is an explicit NOT_RUN/skip unless a separately supplied
fixture is opted in and all local prerequisites are merely present; even then
this unit suite does not claim native PASS.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path
import unittest

from e3_host import q2_namespace_fixture as f


CPU_FIELDS = (
    "usage_usec", "user_usec", "system_usec", "nr_periods", "nr_throttled",
    "throttled_usec", "nr_bursts", "burst_usec",
)
MEMORY_FIELDS = ("low", "high", "max", "oom", "oom_kill", "oom_group_kill")
PIDS_FIELDS = ("max",)


def _schema(kind: str) -> f.CounterSchema:
    return f.CounterSchema.make(
        cpu_fields=CPU_FIELDS,
        memory_event_fields=MEMORY_FIELDS,
        pids_event_fields=PIDS_FIELDS,
        controls=f.controls_for(kind, cpus="7", mems="0"),
    )


def _counter(fields, changes=None):
    values = {name: 0 for name in fields}
    values.update(changes or {})
    return "".join(f"{name} {values[name]}\n" for name in fields).encode("ascii")


def _raw_snapshot(kind: str, *, cpu_usage=0, memory_current=0, memory_peak=0,
                  pids_current=0, pids_peak=0, procs=(), populated=0,
                  frozen=0, descendants=0, dying=0):
    schema = _schema(kind)
    raw = {
        "cgroup.procs": b"".join(f"{pid}\n".encode("ascii") for pid in procs),
        "cgroup.events": f"populated {populated}\nfrozen {frozen}\n".encode("ascii"),
        "cgroup.stat": (
            f"nr_descendants {descendants}\nnr_dying_descendants {dying}\n".encode("ascii")
        ),
        "cpu.stat": _counter(CPU_FIELDS, {"usage_usec": cpu_usage}),
        "memory.current": f"{memory_current}\n".encode("ascii"),
        "memory.peak": f"{memory_peak}\n".encode("ascii"),
        "memory.events": _counter(MEMORY_FIELDS),
        "memory.events.local": _counter(MEMORY_FIELDS),
        "pids.current": f"{pids_current}\n".encode("ascii"),
        "pids.peak": f"{pids_peak}\n".encode("ascii"),
        "pids.events": _counter(PIDS_FIELDS),
    }
    for name, expected in schema.controls:
        if name in {"cgroup.controllers", "cgroup.subtree_control"} and expected:
            expected = " ".join(reversed(expected.split(" ")))
        raw[name] = (expected + "\n").encode("ascii")
    return raw, schema


def _snapshot(kind: str, **changes) -> f.CgroupSnapshot:
    raw, schema = _raw_snapshot(kind, **changes)
    return f.parse_cgroup_snapshot(raw, schema)


def _complete_action(ledger: f.ActionLedger, key, digest="a" * 64,
                     result="SUCCEEDED") -> f.ActionLedger:
    ledger = f.begin_action(ledger, kind=key[0], case_id=key[1], digest=digest)
    for phase in (
        f.ActionPhase.CARRIER_ENTERED,
        f.ActionPhase.OWNER_COMMITTED,
        f.ActionPhase.GUARDIAN_REENTERED,
        f.ActionPhase.SLOT_SEALED,
        f.ActionPhase.RELEASED,
    ):
        ledger = f.advance_action(ledger, phase)
    return f.record_action_attempt(ledger, result=result)


class LayoutTests(unittest.TestCase):
    def test_result_layout_is_exact_and_contiguous(self):
        self.assertEqual((0, 8192), (f.result_region("header").offset,
                                    f.result_region("header").end))
        first = f.result_region("case", 1)
        last = f.result_region("case", 12)
        self.assertEqual((8192, 57344), (first.offset, first.end))
        self.assertEqual(f.RESULT_EXCURSION_OFFSET, last.end)
        self.assertEqual((8192, 40960),
                         (f.result_region("case_stdout", 1).offset,
                          f.result_region("case_stdout", 1).end))
        self.assertEqual((40960, 49152),
                         (f.result_region("case_stderr", 1).offset,
                          f.result_region("case_stderr", 1).end))
        self.assertEqual((49152, 57344),
                         (f.result_region("case_metadata", 1).offset,
                          f.result_region("case_metadata", 1).end))
        self.assertEqual(f.RESULT_TERMINAL_OFFSET, f.result_region("excursion", 38).end)
        self.assertEqual(f.RESULT_JOURNAL_BYTES, f.result_region("terminal").end)
        with self.assertRaises(f.FixtureContractError):
            f.result_region("excursion", 39)

    def test_stage_maximum_and_action_manifest_slots(self):
        bundle = {f"artifact-{index}": 128 * 1024 for index in range(8)}
        layout = f.validate_stage_layout(bundle)
        self.assertEqual(f.STAGE_MAX_LOGICAL_BYTES, layout.logical_bytes)
        self.assertEqual(22, layout.regular_files)
        self.assertEqual(23, layout.inodes_with_directory)
        slots = f.validate_action_slots(tuple((index * 1024, 1024) for index in range(37)))
        self.assertEqual(37, len(slots))
        self.assertLessEqual(slots[-1].end, f.ACTION_JOURNAL_BYTES)
        with self.assertRaises(f.FixtureContractError):
            f.validate_action_slots(tuple((0, 1024) for _ in range(37)))

    def test_stage_rejects_escape_reserved_and_budget_growth(self):
        for bundle in ({}, {"../escape": 1}, {"action.journal": 1},
                       {"a": 1024 * 1024, "b": 1},
                       {f"x{i}": 1 for i in range(9)}):
            with self.subTest(bundle=bundle), self.assertRaises(f.FixtureContractError):
                f.validate_stage_layout(bundle)


class CounterAndReclaimTests(unittest.TestCase):
    def test_strict_initial_and_final_snapshots(self):
        initial = _snapshot("case")
        self.assertIs(initial, f.validate_initial_snapshot(initial))
        final = _snapshot("case", cpu_usage=5_000_000,
                          memory_peak=128 * 1024 * 1024, pids_peak=3)
        self.assertIs(final, f.validate_final_snapshot(final, "case"))

    def test_snapshot_parser_rejects_unknown_missing_order_and_noncanonical_numbers(self):
        raw, schema = _raw_snapshot("guardian")
        bad = dict(raw)
        bad["surprise"] = b"0\n"
        with self.assertRaisesRegex(f.FixtureContractError, "FIXTURE_SNAPSHOT_FILES"):
            f.parse_cgroup_snapshot(bad, schema)
        bad = dict(raw)
        bad["cpu.stat"] = b"user_usec 0\nusage_usec 0\n" + raw["cpu.stat"].split(b"\n", 2)[2]
        with self.assertRaises(f.FixtureContractError):
            f.parse_cgroup_snapshot(bad, schema)
        bad = dict(raw)
        bad["memory.current"] = b"00\n"
        with self.assertRaises(f.FixtureContractError):
            f.parse_cgroup_snapshot(bad, schema)
        bad = dict(raw)
        bad["cgroup.type"] = "domäin\n"
        with self.assertRaises(f.FixtureContractError):
            f.parse_cgroup_snapshot(bad, schema)

    def test_initial_nonzero_and_final_ceiling_or_liveness_fail_closed(self):
        with self.assertRaisesRegex(f.FixtureContractError, "INITIAL_COUNTER_NONZERO"):
            f.validate_initial_snapshot(_snapshot("case", memory_peak=1))
        with self.assertRaisesRegex(f.FixtureContractError, "FINAL_CPU_CEILING"):
            f.validate_final_snapshot(_snapshot("case", cpu_usage=5_000_001), "case")
        with self.assertRaisesRegex(f.FixtureContractError, "FINAL_TASKS"):
            f.validate_final_snapshot(_snapshot("case", procs=(123,), populated=1), "case")
        with self.assertRaisesRegex(f.FixtureContractError, "FINAL_DESCENDANTS"):
            f.validate_final_snapshot(_snapshot("batch", dying=1), "batch")

    def test_reclaim_zero_eagain_partial_and_four_round_limit(self):
        self.assertEqual(f.ReclaimStatus.COMPLETE, f.begin_reclaim(0).status)
        state = f.begin_reclaim(9)
        state = f.reclaim_round(state, observed_before=9, payload=b"9",
                                write_errno=errno.EAGAIN, observed_after=0)
        self.assertEqual(f.ReclaimStatus.COMPLETE, state.status)

        partial = f.reclaim_round(f.begin_reclaim(10), observed_before=10, payload=b"10",
                                  write_errno=None, bytes_written=1, observed_after=5)
        self.assertEqual((f.ReclaimStatus.FAILED, "FIXTURE_RECLAIM_PARTIAL_WRITE"),
                         (partial.status, partial.reason))

        state = f.begin_reclaim(16)
        for before, after in ((16, 12), (12, 8), (8, 4), (4, 1)):
            state = f.reclaim_round(state, observed_before=before,
                                    payload=str(before).encode(), write_errno=None,
                                    observed_after=after)
        self.assertEqual((f.ReclaimStatus.FAILED, 4), (state.status, len(state.rounds)))
        with self.assertRaises(f.FixtureContractError):
            f.require_reclaimed(state)


class TimingAndIssuanceTests(unittest.TestCase):
    def test_case_boundaries_are_absolute_and_do_not_borrow(self):
        clock = f.CaseClock("N01", 100, 200)
        points = (
            (f.CASE_WORK_NS - 1, f.CasePhase.WORK),
            (f.CASE_WORK_NS, f.CasePhase.STOP),
            (f.CASE_STOP_NS, f.CasePhase.DRAIN),
            (f.CASE_DRAIN_NS, f.CasePhase.FINAL),
            (f.CASE_FINAL_NS, f.CasePhase.EXPIRED),
        )
        for elapsed, expected in points:
            with self.subTest(elapsed=elapsed):
                self.assertIs(expected, f.case_phase(
                    clock, boottime_ns=100 + elapsed, monotonic_ns=200 + elapsed))
        self.assertIs(f.CasePhase.STOP, f.case_phase(
            clock, boottime_ns=100, monotonic_ns=200 + f.CASE_WORK_NS))
        with self.assertRaises(f.FixtureContractError):
            f.require_case_operation(clock, operation=f.CaseOperation.OBSERVE,
                                     boottime_ns=100 + f.CASE_WORK_NS,
                                     monotonic_ns=200 + f.CASE_WORK_NS)

    def test_case_reserve_and_twelve_case_sequence(self):
        sequence = f.CaseSequence()
        for index, case_id in enumerate(f.CASE_IDS):
            t0 = index * 200 * f.NS
            sequence = f.start_case(
                sequence, case_id=case_id, t0_boottime_ns=t0,
                t0_monotonic_ns=t0 + 1,
                work_deadline_boottime_ns=t0 + 150 * f.NS,
                work_deadline_monotonic_ns=t0 + 1 + 150 * f.NS,
            )
            sequence = f.close_case(
                sequence, case_id=case_id,
                boottime_ns=t0 + f.CASE_DRAIN_NS,
                monotonic_ns=t0 + 1 + f.CASE_DRAIN_NS,
                outcome="PASSED",
            )
        self.assertEqual(12, len(sequence.completed))
        with self.assertRaises(f.FixtureContractError):
            f.start_case(sequence, case_id="N12", t0_boottime_ns=0,
                         t0_monotonic_ns=0, work_deadline_boottime_ns=200 * f.NS,
                         work_deadline_monotonic_ns=200 * f.NS)
        clock = f.CaseClock("N01", 0, 0)
        with self.assertRaisesRegex(f.FixtureContractError, "FIXTURE_CASE_RESERVE"):
            f.require_case_reserve(
                clock, boottime_ns=0, monotonic_ns=0,
                work_deadline_boottime_ns=150 * f.NS - 1,
                work_deadline_monotonic_ns=150 * f.NS,
            )

    def test_issuance_is_monotonic_and_clean_rejection_needs_closure(self):
        state = f.issue_delivery(f.IssuanceState())
        with self.assertRaises(f.FixtureContractError):
            f.issue_delivery(state)
        with self.assertRaises(f.FixtureContractError):
            f.finish_release(state, f.ReleaseOutcome.CLEAN_REJECTED)
        rejected = f.finish_release(state, f.ReleaseOutcome.CLEAN_REJECTED,
                                    clean_closure_complete=True)
        self.assertIs(f.Qualification.BLOCKED_RETAINED, rejected.qualification)
        self.assertTrue(rejected.delivery_issued)
        self.assertTrue(rejected.modeled_only)
        self.assertFalse(rejected.durability_proven)
        self.assertFalse(rejected.live_proven)
        with self.assertRaises(f.FixtureContractError):
            f.issue_batch_release(rejected, owner_record_fsynced=True)

    def test_one_batch_release_and_terminal_qualification(self):
        with self.assertRaisesRegex(f.FixtureContractError, "PURE_MODEL_LIVE_MATCH"):
            f.IssuanceState(
                qualification=f.Qualification.FIXTURE_LIVE_REFERENCE_MATCHED
            )
        for invalid in ("FIXTURE_LIVE_REFERENCE_MATCHED", "NOT_RUN"):
            with self.assertRaisesRegex(f.FixtureContractError,
                                        "PURE_MODEL_LIVE_MATCH"):
                f.IssuanceState(qualification=invalid)
        with self.assertRaisesRegex(f.FixtureContractError, "PURE_MODEL_LIVE_MATCH"):
            f.IssuanceState(batch_release_outcome="NOT_SENT")
        with self.assertRaisesRegex(f.FixtureContractError, "PURE_MODEL_LIVE_MATCH"):
            f.IssuanceState(delivery_issued=1)
        state = f.issue_delivery(f.IssuanceState())
        with self.assertRaises(f.FixtureContractError):
            f.issue_batch_release(state, owner_record_fsynced=False)
        state = f.issue_batch_release(state, owner_record_fsynced=True)
        with self.assertRaises(f.FixtureContractError):
            f.issue_batch_release(state, owner_record_fsynced=True)
        state = f.accept_batch_release(state, owner_capture_fsynced=True)
        with self.assertRaisesRegex(f.FixtureContractError, "FIXTURE_QUALIFICATION"):
            f.finish_fixture(state, f.Qualification.FIXTURE_LIVE_REFERENCE_MATCHED,
                             complete_evidence=True)
        done = f.finish_fixture(state, f.Qualification.FAILED_RETAINED,
                                complete_evidence=True)
        self.assertIs(f.ReleaseOutcome.ACCEPTED, done.batch_release_outcome)
        with self.assertRaises(f.FixtureContractError):
            f.finish_fixture(done, f.Qualification.UNKNOWN_RETAINED,
                             complete_evidence=False)


class ActionAndCpuTests(unittest.TestCase):
    def test_full_action_plan_has_37_commits_and_exact_76_self_writes(self):
        ledger = f.enter_initial_guardian(f.ActionLedger())
        for index, key in enumerate(f.ACTION_PLAN):
            ledger = _complete_action(ledger, key, digest=f"{index + 1:064x}")
        self.assertEqual((37, 37, 38, 75),
                         (len(ledger.records), ledger.carrier_writes,
                          ledger.guardian_writes, ledger.self_writes))
        bits = f.issued_action_bits(ledger)
        self.assertTrue(bits["modeled_only"])
        self.assertFalse(bits["durability_proven"])
        self.assertFalse(bits["live_proven"])
        self.assertTrue(bits["fixture_native_batch_issued"])
        self.assertTrue(all(all(case.values()) for case in bits["cases"].values()))
        ledger = f.enter_final_carrier(ledger, write_performed=True)
        self.assertEqual((38, 38, 76),
                         (ledger.carrier_writes, ledger.guardian_writes, ledger.self_writes))
        with self.assertRaises(f.FixtureContractError):
            f.enter_final_carrier(ledger, write_performed=True)

    def test_action_order_commit_bit_and_failure_location_are_fail_closed(self):
        ledger = f.enter_initial_guardian(f.ActionLedger())
        with self.assertRaisesRegex(f.FixtureContractError, "FIXTURE_ACTION_ORDER"):
            f.begin_action(ledger, kind="clone", case_id="N01", digest="a" * 64)
        ledger = f.begin_action(ledger, kind="native_batch", case_id="N01", digest="a" * 64)
        self.assertTrue(f.issued_action_bits(ledger)["fixture_native_batch_issued"])
        ledger = f.advance_action(ledger, f.ActionPhase.CARRIER_ENTERED)
        ledger = f.advance_action(ledger, f.ActionPhase.OWNER_COMMITTED)
        self.assertTrue(f.issued_action_bits(ledger)["fixture_native_batch_issued"])
        ledger = f.fail_action(ledger, reason="ACK_LOST")
        with self.assertRaises(f.FixtureContractError):
            f.begin_action(ledger, kind="clone", case_id="N01", digest="b" * 64)
        ledger = f.enter_final_carrier(ledger, write_performed=False)
        self.assertEqual(1, ledger.carrier_writes)

        before_move = f.enter_initial_guardian(f.ActionLedger())
        before_move = f.begin_action(before_move, kind="native_batch", case_id="N01",
                                     digest="a" * 64)
        before_move = f.fail_action(before_move, reason="MIGRATION_FAILED")
        self.assertTrue(f.issued_action_bits(before_move)["fixture_native_batch_issued"])
        before_move = f.enter_final_carrier(before_move, write_performed=True)
        self.assertEqual((f.Membership.CARRIER, 1),
                         (before_move.membership, before_move.carrier_writes))

    def test_cpu_rounding_migration_double_charge_and_exec_continuity(self):
        ledger = f.begin_cpu_ledger(sample_ns=100, membership=f.Membership.CARRIER,
                                    rounding_ns=10)
        self.assertEqual(110, ledger.carrier_ns)
        ledger = f.charge_cpu(ledger, sample_ns=200, membership=f.Membership.CARRIER)
        ledger = f.migrate_cpu(ledger, before_ns=250, after_ns=300,
                               to_membership=f.Membership.GUARDIAN)
        self.assertEqual((340, 60), (ledger.carrier_ns, ledger.guardian_ns))
        ledger = f.charge_cpu(ledger, sample_ns=400, membership=f.Membership.GUARDIAN)
        self.assertEqual(170, ledger.guardian_ns)

        resumed = f.begin_cpu_ledger(sample_ns=100, membership=f.Membership.CARRIER,
                                     rounding_ns=10)
        resumed = f.cpu_handoff(resumed, sample_ns=200)
        resumed = f.cpu_resume_after_exec(resumed, sample_ns=300)
        resumed = f.charge_cpu(resumed, sample_ns=400, membership=f.Membership.CARRIER)
        self.assertEqual(440, resumed.carrier_ns)
        with self.assertRaises(f.FixtureContractError):
            f.cpu_resume_after_exec(resumed, sample_ns=500)

    def test_cpu_success_limits_and_segment_expiry(self):
        ledger = f.begin_cpu_ledger(sample_ns=0, membership=f.Membership.CARRIER,
                                    rounding_ns=1)
        expiry = f.segment_expiry(
            ledger, now_process_ns=0,
            envelope_ns={"guardian": 200, "carrier": 100, "process": 150},
            stop_reserve_ns={"guardian": 1, "carrier": 1, "process": 1},
            fatal_overshoot_ns=10, normal_worst_ns=80,
        )
        self.assertEqual(90, expiry)
        with self.assertRaisesRegex(f.FixtureContractError, "FIXTURE_CPU_FATAL_EXPIRY"):
            f.segment_expiry(
                ledger, now_process_ns=0,
                envelope_ns={"guardian": 200, "carrier": 100, "process": 150},
                stop_reserve_ns={"guardian": 1, "carrier": 1, "process": 1},
                fatal_overshoot_ns=10, normal_worst_ns=90,
            )
        with self.assertRaisesRegex(f.FixtureContractError, "SUCCESS_CROSSCHECK"):
            f.validate_cpu_limits(ledger, success=True, tail_cpu_ns=1)
        f.validate_cpu_limits(ledger, success=True, tail_cpu_ns=1,
                              guardian_cpu_stat_usec=9_000_000)


class TreeAndNativeTests(unittest.TestCase):
    def test_controls_require_one_canonical_cpu(self):
        self.assertEqual("7", f.controls_for("case", cpus="7")["cpuset.cpus.effective"])
        for cpus in ("", "00", "07", "0-7", "0,1", " 7", "7\n"):
            with self.subTest(cpus=cpus), self.assertRaisesRegex(
                    f.FixtureContractError, "FIXTURE_CPUSET"):
                f.controls_for("case", cpus=cpus)

    def test_tree_requires_initial_zero_then_closes_all_twelve_sequentially(self):
        tree = f.new_tree(anchor_d0=17)
        with self.assertRaisesRegex(f.FixtureContractError, "CHILD_BEFORE_BATCH"):
            f.create_node(tree, "guardian")
        tree = f.create_node(tree, "batch")
        tree = f.configure_node(tree, "batch")
        tree = f.enable_batch_controllers(tree)
        tree = f.verify_node_initial(tree, "batch", _snapshot("batch"))
        for kind in ("guardian", "supervisor"):
            tree = f.create_node(tree, kind)
            tree = f.configure_node(tree, kind)
            tree = f.verify_node_initial(tree, kind, _snapshot(kind))
            tree = f.occupy_leaf(tree, kind)
        for case_id in f.CASE_IDS:
            tree = f.create_node(tree, "case", case_id=case_id)
            tree = f.configure_node(tree, "case")
            tree = f.verify_node_initial(tree, "case", _snapshot("case"))
            tree = f.occupy_leaf(tree, "case")
            tree = f.empty_leaf(tree, "case")
            tree = f.reclaim_node(tree, "case", f.begin_reclaim(0))
            tree = f.verify_node_final(
                tree, "case", _snapshot("case", cpu_usage=5_000_000,
                                        memory_peak=128 * 1024 * 1024, pids_peak=3))
            tree = f.remove_node(tree, "case")
            tree = f.close_node(tree, "case", parent_dying_descendants=0)
        for kind in ("supervisor", "guardian"):
            tree = f.empty_leaf(tree, kind)
            tree = f.reclaim_node(tree, kind, f.begin_reclaim(0))
            tree = f.verify_node_final(tree, kind, _snapshot(kind))
            tree = f.remove_node(tree, kind)
            tree = f.close_node(tree, kind, parent_dying_descendants=0)
        tree = f.reclaim_node(tree, "batch", f.begin_reclaim(0))
        tree = f.verify_node_final(tree, "batch", _snapshot("batch"))
        tree = f.remove_node(tree, "batch")
        with self.assertRaisesRegex(f.FixtureContractError, "ANCHOR_NOT_RESTORED"):
            f.close_node(tree, "batch", parent_dying_descendants=0,
                         anchor_descendants=18)
        tree = f.close_node(tree, "batch", parent_dying_descendants=0,
                            anchor_descendants=17)
        self.assertIs(tree, f.validate_tree_success(tree))

    def test_parent_dying_and_active_case_block_teardown(self):
        tree = f.new_tree(anchor_d0=0)
        tree = f.create_node(tree, "batch")
        tree = f.configure_node(tree, "batch")
        tree = f.enable_batch_controllers(tree)
        tree = f.verify_node_initial(tree, "batch", _snapshot("batch"))
        for kind in ("guardian", "supervisor"):
            tree = f.create_node(tree, kind)
            tree = f.configure_node(tree, kind)
            tree = f.verify_node_initial(tree, kind, _snapshot(kind))
            tree = f.occupy_leaf(tree, kind)
        tree = f.create_node(tree, "case", case_id="N01")
        with self.assertRaisesRegex(f.FixtureContractError, "SUPERVISOR_HAS_CASE"):
            f.empty_leaf(tree, "supervisor")

    def test_native_capability_never_claims_pass(self):
        absent = f.native_capability(explicit_fixture=False, linux=True, root=True,
                                     cgroup2=True, cgroup_writable=True, bridge_built=True)
        self.assertEqual(("NOT_RUN", False), (absent.status, absent.native_pass))
        eligible = f.native_capability(explicit_fixture=True, linux=True, root=True,
                                       cgroup2=True, cgroup_writable=True, bridge_built=True)
        self.assertEqual(("ELIGIBLE_NOT_EXECUTED", False),
                         (eligible.status, eligible.native_pass))
        with self.assertRaisesRegex(f.FixtureContractError,
                                    "FIXTURE_NATIVE_PASS_FORBIDDEN"):
            f.NativeCapability("ELIGIBLE_NOT_EXECUTED", "EXTERNAL_FIXTURE", True)
        with self.assertRaisesRegex(f.FixtureContractError,
                                    "FIXTURE_NATIVE_STATUS"):
            f.NativeCapability("PASS", "EXTERNAL_FIXTURE")

    def test_native_fixture_is_explicitly_not_run_here(self):
        opted_in = os.environ.get("LH_Q2_NAMESPACE_NATIVE_FIXTURE") == "1"
        cgroup2 = Path("/sys/fs/cgroup/cgroup.controllers").is_file()
        writable = os.access("/sys/fs/cgroup", os.W_OK)
        capability = f.native_capability(
            explicit_fixture=opted_in,
            linux=os.name == "posix" and Path("/proc/self").is_dir(),
            root=getattr(os, "geteuid", lambda: -1)() == 0,
            cgroup2=cgroup2,
            cgroup_writable=writable,
            bridge_built=False,
        )
        self.skipTest(f"{capability.status}: {capability.reason}; unit suite performs no native mutation")


if __name__ == "__main__":
    unittest.main()
