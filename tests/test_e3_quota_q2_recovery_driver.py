"""Recovery authority, original first issuance and finite-window integration."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_e3_quota_q2_prepare_driver import fixture as original_fixture, ModelFiles

PATH = Path(__file__).parent / "e3_host/q2_recovery_driver.py"
spec = importlib.util.spec_from_file_location("q2_recovery_driver_test", PATH)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def fixture():
    plan, old = original_fixture()
    plan["budgets"] = dict(state_bytes=32*1024**2, state_inodes=4096, capture_bytes=64*1024**2, capture_inodes=4096)
    recovery = dict(schema="local-hand-q2-preparation-recovery-plan/v1", scope="LH-Q2-PREP-RECOVERY-v1",
        baseline="72c06ec68d370333f5ffb1079023917828b3e681", recovery_id="restore001",
        preparation_id=plan["preparation_id"], original_files={"preparation-result.json": "a" * 64},
        recovery_source=dict(commit="b" * 40, tree="c" * 40, files={"/recovery/tools.py": "d" * 64}))
    observed = copy.deepcopy(old["facts"])
    receipt = dict(schema="local-hand-q2-preparation-recovery/v1", status="RESOURCES_RECOVERED",
        fixture_generated=False, q2_accepted=False, q3_accepted=False, production_supported=False,
        preparation_id=plan["preparation_id"], plan_sha256=r.sha(r.encoded(plan)), facts=observed,
        recovery=dict(id=recovery["recovery_id"], plan_sha256=r.sha(r.encoded(recovery)), source=recovery["recovery_source"],
            original_receipt_sha256="a" * 64, attested=True, original_files_preserved=True,
            directory=dict(path=plan["directories"]["reservation"]["path"] + "/restore001", device=70, inode=8800)))
    entry, guest = clock_fixture(observed["host"]["boot_id"])
    return plan, recovery, receipt, entry, guest


def clock_fixture(boot_id="11111111-2222-3333-4444-555555555555"):
    entry = dict(monotonic_ns=50 * 10**9, boottime_ns=1000 * 10**9)
    guest = dict(schema=r.DELIVERY_SCHEMA, recovery_id="restore001", boot_id=boot_id,
        issued_ns=999 * 10**9, deadline_ns=1269 * 10**9, stop_ns=3 * 10**9, guest_outer_deadline_ns=1280 * 10**9, clock_anchor_sha256="e" * 64, preparation_deadline_ns=1139 * 10**9)
    return entry, guest


def costs():
    return {role: dict(bytes=0, inodes=0) for role in ("state", "capture")}


def ledger_command(plan, files, calls):
    def command(args):
        from local_hand_jobs.policy import Policy
        from local_hand_jobs.state import StateStore
        calls.append(args)
        config = files.writes[args[args.index("--initialize-ledger") + 1]][0]
        policy = Policy(config)
        with tempfile.TemporaryDirectory() as temporary:
            store = StateStore(Path(temporary) / "jobs.sqlite", policy.authority_id,
                plan["settings"]["identity"]["ledger_id"], initialize=True)
            try:
                with store.transaction() as tx:
                    if store.all(tx): raise AssertionError("nonempty original ledger")
                    generation = tx.execute("SELECT value FROM counters WHERE key='generation'").fetchone()[0]
            finally:
                store.close()
        return r.encoded(dict(path=config["broker_root"] + "/jobs.sqlite", device=70, inode=999,
            uid=plan["account"]["uid"], mode=0o600, ledger_id=plan["settings"]["identity"]["ledger_id"],
            generation=[policy.generation, generation]))
    return command


@unittest.skipUnless(sys.platform.startswith("linux"), "Q2 Linux administrative receipt and policy assembly")
class RecoveryDriverTests(unittest.TestCase):
    def test_delivery_recovery_receipt_and_assembly_share_bootstrap_deadline(self):
        """Real helper schemas/assembly/SQLite, with explicit modeled OS facts."""
        from test_e3_quota_q2_prepare_contract import fixture as full_plan
        from test_e3_quota_q2_prepare_recovery import recovery_fixture, m as recovery_module, ModelBackend
        delivery_module = r.helper("q2_recovery_delivery")
        plan = full_plan()
        ordinary_plan, old_observed = original_fixture()
        observed = copy.deepcopy(old_observed["facts"])
        plan["settings"] = ordinary_plan["settings"]
        plan["tools"]["setpriv"] = ordinary_plan["tools"]["setpriv"]
        plan["settings"]["identity"]["expires_at"] = 1
        observed["ordinary"] = dict(plan["account"])
        observed["parents"]["ordinary"]["path"] = "/user.slice/user-1100.slice/user@1100.service/q2work.slice"
        plan["host"].update(observed["host"])
        for name in ("commit", "tree"):
            plan["candidate"][name] = observed["installation"]["source"][name]
        observed["installation"]["source"]["root"] = plan["candidate"]["source"]
        observed["installation"]["admin"]["entry"]["path"] = (
            plan["candidate"]["source"] + "/tools/admin/local_hand_quota_observer/q2_entry.py")
        for name, value in plan["directories"].items():
            observed["directories"][name]["path"] = value["path"]
            observed["directories"][name]["uid"] = 1100 if value["owner"] == "ordinary" else 0
            observed["directories"][name]["gid"] = 1100 if value["owner"] == "ordinary" else 0
        for planned, measured in zip(plan["roots"], observed["roots"]):
            planned["hard_bytes"] = 1024**2
            measured.update(planned)
            measured.update(uid=1100, gid=1100)
            measured["filesystem_uuid"] = plan["mounts"]["quota"]["uuid"]
        plan, recovery, raw = recovery_fixture(plan)
        original_bytes = dict(raw)
        observed["retained_before"] = recovery_module.c.document(raw["preflight.json"])["retained_before"]
        observed["retained_after"] = observed["retained_before"]
        boot_id = plan["host"]["boot_id"]
        anchor = delivery_module.make_clock_anchor(host_issued_ns=100*10**9, host_deadline_ns=400*10**9,
            host_probe_send_ns=101*10**9, host_probe_receive_ns=103*10**9,
            guest_boot_id=boot_id, expected_boot_id=boot_id, guest_sample_ns=1000*10**9)
        guest = delivery_module.guest_envelope(anchor, recovery_id=recovery["recovery_id"],
            guest_boot_id=boot_id, guest_now_ns=1002*10**9)
        # Bootstrap consumed 32 seconds before the driver began. None is refunded.
        entry = dict(monotonic_ns=1034*10**9, boottime_ns=1034*10**9)
        with mock.patch.object(Path, "read_text", return_value=boot_id):
            self.assertEqual(guest, r.delivery(delivery_module.encoded(guest),
                delivery_module.sha(delivery_module.encoded(guest)), recovery["recovery_id"], entry))
        issued, deadline = r.preparation_window(guest, entry)
        self.assertEqual(1002*10**9, issued)
        self.assertEqual(1142*10**9, deadline)
        self.assertEqual(108*10**9, deadline-entry["monotonic_ns"])

        class ObservedBackend(ModelBackend):
            def preflight(self):
                recovery_module.verify_records(plan, recovery, raw)
                return {key: observed[key] for key in ("host", "mounts", "retained_before", "capacity_observed")}
            def account(self): return observed["ordinary"]
            def directories(self): return observed["directories"]
            def install(self): return observed["installation"]
            def roots(self): return observed["roots"]
            def parents(self): return observed["parents"]
            def snapshot(self): return observed["retained_before"]

        backend = ObservedBackend()
        backend.recovery_directory = dict(path=plan["directories"]["reservation"]["path"] + "/" + recovery["recovery_id"],
            device=11, inode=8)
        receipt = recovery_module.recover(plan, recovery, backend,
            validate_settings=lambda _: r.helper("q2_prepare_driver").validate_plan(plan),
            issued_ns=issued, deadline_ns=deadline)
        self.assertEqual("RESOURCES_RECOVERED", receipt["status"])
        self.assertEqual(deadline, receipt["recovery"]["deadline_ns"])
        self.assertEqual(original_bytes, raw)
        self.assertEqual("INCOMPLETE", recovery_module.c.document(raw["preparation-result.json"])["status"])
        before_plan, before_receipt = r.encoded(plan), r.encoded(receipt)
        files = ModelFiles(); calls = []
        now = dict(boot_id=boot_id, boottime_ns=1060*10**9)
        prepared, invocation = r.complete(plan, recovery, receipt, files=files, measure_costs=costs,
            command=ledger_command(plan, files, calls), clock=lambda: now, entry=entry,
            delivery_envelope=guest, verify_preserved=backend.verify_preserved,
            wall_clock=lambda: 1800000000*10**9)
        handoff = files.writes[invocation[invocation.index("--plan")+1]][0]
        self.assertEqual(guest, files.writes[backend.recovery_directory["path"] + "/delivery-envelope.json"][0])
        self.assertEqual(1, prepared["first_request_issuance"]["old_template_expires_at"])
        self.assertEqual(before_plan, r.encoded(plan)); self.assertEqual(before_receipt, r.encoded(receipt))
        self.assertEqual(1, len(calls))
        self.assertLess(handoff["owner_envelope"]["deadline_ns"] + 8*10**9, guest["deadline_ns"])
        self.assertGreater(delivery_module.remaining(guest, anchor,
            guest_boot_id=boot_id, guest_now_ns=now["boottime_ns"]), 128*10**9)

    def test_recovered_assembly_preserves_failure_and_pins_actual_first_request(self):
        plan, recovery, receipt, entry, guest = fixture()
        plan["settings"]["identity"]["expires_at"] = 1
        receipt["plan_sha256"] = r.sha(r.encoded(plan))
        original_plan, original_receipt = r.encoded(plan), r.encoded(receipt)
        files = ModelFiles(); calls = []; preserved = []
        clock = lambda: dict(boot_id=guest["boot_id"], boottime_ns=1001 * 10**9)
        prepared, invocation = r.complete(plan, recovery, receipt, files=files, measure_costs=costs,
            command=ledger_command(plan, files, calls), clock=clock, entry=entry,
            delivery_envelope=guest, verify_preserved=lambda: preserved.append(True),
            wall_clock=lambda: 1800000000 * 10**9)
        self.assertEqual("RECOVERED_PREPARED", prepared["status"])
        self.assertEqual(original_plan, r.encoded(plan))
        self.assertEqual(original_receipt, r.encoded(receipt))
        self.assertEqual([True, True], preserved)
        self.assertEqual(1, len(calls))
        self.assertTrue(calls[0][11].endswith("/q2_prepare_driver.py"))
        handoff = files.writes[invocation[invocation.index("--plan") + 1]][0]
        request = handoff["template"]["launcher"]["resident"]["request"]
        self.assertEqual(1800000120, request["expires_at"])
        self.assertEqual(plan["settings"]["identity"]["operation_id"], request["operation_id"])
        from local_hand_jobs.contract import request_digest
        self.assertEqual(request_digest(request), request["request_digest"])
        self.assertEqual(request["request_digest"], prepared["request_digest"])
        directory = receipt["recovery"]["directory"]["path"]
        authority = files.writes[directory + "/authority.json"][0]
        self.assertEqual(r.AUTHORITY_SCHEMA, authority["schema"])
        self.assertEqual("a" * 64, authority["original_failure_sha256"])
        self.assertEqual(1, authority["first_request_issuance"]["old_template_expires_at"])
        self.assertEqual(prepared["authority_sha256"], r.sha(r.encoded(authority)))
        self.assertEqual(120 * 10**9, handoff["owner_envelope"]["deadline_ns"] - handoff["owner_envelope"]["issued_ns"])
        self.assertLess(handoff["owner_envelope"]["deadline_ns"] + r.STOP_NS + r.FINALIZATION_NS, guest["deadline_ns"])
        self.assertFalse(any(name.endswith("preparation-result.json") for name in files.writes))
        self.assertEqual(1, len([name for name in files.writes if name.endswith("first-request-issuance.json")]))
        self.assertTrue(invocation[3].endswith("/q2_prepare_run.py"))
        with self.assertRaises(FileExistsError):
            r.complete(plan, recovery, receipt, files=files, measure_costs=costs, command=lambda _: self.fail("ledger replay"),
                clock=clock, entry=entry, delivery_envelope=guest, verify_preserved=lambda: None,
                wall_clock=lambda: 1800000010 * 10**9)

    def test_failed_or_changed_recovery_cannot_create_children(self):
        for fault in ("schema", "accepted", "status", "source", "plan", "original", "attested", "preserved", "retained", "account"):
            plan, recovery, receipt, entry, guest = fixture(); files = ModelFiles()
            if fault == "schema": receipt["schema"] = "local-hand-q2-fixture-preparation/v1"
            elif fault == "accepted": receipt["q2_accepted"] = True
            elif fault == "status": receipt["status"] = "INCOMPLETE"
            elif fault == "source": receipt["recovery"]["source"] = {"commit": "e" * 40}
            elif fault == "plan": receipt["plan_sha256"] = "e" * 64
            elif fault == "original": receipt["recovery"]["original_receipt_sha256"] = "e" * 64
            elif fault == "attested": receipt["recovery"]["attested"] = False
            elif fault == "preserved": receipt["recovery"]["original_files_preserved"] = False
            elif fault == "retained": receipt["facts"]["retained_after"] = []
            else: receipt["facts"]["ordinary"]["uid"] += 1
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                r.complete(plan, recovery, receipt, files=files, measure_costs=costs, command=lambda _: self.fail("command"),
                    clock=lambda: dict(boot_id=guest["boot_id"], boottime_ns=1001 * 10**9),
                    entry=entry, delivery_envelope=guest, verify_preserved=lambda: self.fail("preserve"))
            self.assertFalse(files.dirs); self.assertFalse(files.writes)

    def test_expired_or_unfunded_nested_windows_fail_before_issuance(self):
        for fault in ("entry", "guest", "boot"):
            plan, recovery, receipt, entry, guest = fixture(); files = ModelFiles()
            now = dict(boot_id=guest["boot_id"], boottime_ns=1001 * 10**9)
            if fault == "entry": now["boottime_ns"] = entry["boottime_ns"] + r.PREPARATION_NS
            elif fault == "guest": guest["deadline_ns"] = now["boottime_ns"] + 127 * 10**9
            else: now["boot_id"] = "changed"
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                r.complete(plan, recovery, receipt, files=files, measure_costs=costs, command=lambda _: self.fail("command"),
                    clock=lambda: now, entry=entry, delivery_envelope=guest, verify_preserved=lambda: None)
            self.assertFalse(files.writes); self.assertFalse(files.dirs)

    def test_late_assembly_does_not_issue_owner(self):
        plan, recovery, receipt, entry, guest = fixture(); files = ModelFiles(); calls = []
        clocks = iter([1001, 1002, 1140])
        with self.assertRaisesRegex(ValueError, "PREPARATION_EXPIRED"):
            r.complete(plan, recovery, receipt, files=files, measure_costs=costs, command=ledger_command(plan, files, calls),
                clock=lambda: dict(boot_id=guest["boot_id"], boottime_ns=next(clocks) * 10**9),
                entry=entry, delivery_envelope=guest, verify_preserved=lambda: None,
                wall_clock=lambda: 1800000000 * 10**9)
        self.assertEqual(1, len(calls))
        self.assertTrue(any(name.endswith("first-request-issuance.json") for name in files.writes))
        self.assertFalse(any(name.endswith("handoff.json") for name in files.writes))

    def test_original_files_drift_blocks_owner(self):
        plan, recovery, receipt, entry, guest = fixture(); files = ModelFiles()
        def changed(): raise ValueError("ORIGINAL_CHANGED")
        with self.assertRaisesRegex(ValueError, "ORIGINAL_CHANGED"):
            r.complete(plan, recovery, receipt, files=files, measure_costs=costs, command=ledger_command(plan, files, []),
                clock=lambda: dict(boot_id=guest["boot_id"], boottime_ns=1001 * 10**9),
                entry=entry, delivery_envelope=guest, verify_preserved=changed,
                wall_clock=lambda: 1800000000 * 10**9)
        self.assertFalse(any(name.endswith("handoff.json") for name in files.writes))

    def test_assembly_reservation_counts_existing_bytes_and_inodes_before_writes(self):
        for category, key in (("state", "bytes"), ("state", "inodes"), ("capture", "bytes"), ("capture", "inodes")):
            plan, recovery, receipt, entry, guest = fixture(); files = ModelFiles()
            measured = costs()
            measured[category][key] = plan["budgets"][category + "_" + key]
            with self.subTest(category=category, key=key), self.assertRaisesRegex(ValueError, "ASSEMBLY_CAPACITY"):
                r.complete(plan, recovery, receipt, files=files, measure_costs=lambda: measured,
                    command=lambda _: self.fail("ledger issued without capacity"),
                    clock=lambda: dict(boot_id=guest["boot_id"], boottime_ns=1001*10**9),
                    entry=entry, delivery_envelope=guest, verify_preserved=lambda: None)
            self.assertFalse(files.dirs); self.assertFalse(files.writes)

    def test_final_handoff_is_measured_before_runtime_can_be_issued(self):
        plan, recovery, receipt, entry, guest = fixture(); files = ModelFiles(); checks = []
        def verify():
            checks.append(True)
            if len(checks) == 2:
                self.assertTrue(any(name.endswith("handoff.json") for name in files.writes))
                raise ValueError("RECOVERY_TOTAL_CAPACITY")
        with self.assertRaisesRegex(ValueError, "RECOVERY_TOTAL_CAPACITY"):
            r.complete(plan, recovery, receipt, files=files, measure_costs=costs,
                command=ledger_command(plan, files, []),
                clock=lambda: dict(boot_id=guest["boot_id"], boottime_ns=1001*10**9),
                entry=entry, delivery_envelope=guest, verify_preserved=verify,
                wall_clock=lambda: 1800000000*10**9)
        self.assertEqual(2, len(checks))


class ClockAndEntryTests(unittest.TestCase):
    def test_bootstrap_elapsed_time_and_suspend_are_not_refunded(self):
        entry, guest = clock_fixture()
        late_entry = dict(entry, monotonic_ns=entry["monotonic_ns"] + 130*10**9,
            boottime_ns=entry["boottime_ns"] + 130*10**9)
        self.assertEqual(r.preparation_window(guest, entry), r.preparation_window(guest, late_entry))
        original_guard = mock.Mock()
        # MONOTONIC still permits progress after suspend; BOOTTIME does not.
        guard = r.preparation_guard(original_guard, guest,
            lambda: dict(boot_id=guest["boot_id"], boottime_ns=guest["preparation_deadline_ns"]))
        with self.assertRaisesRegex(ValueError, "RECOVERY_DRIVER_PREPARATION_EXPIRED"):
            guard()
        original_guard.assert_called_once()

    def test_delivery_absolute_window_has_no_renewal(self):
        entry, guest = clock_fixture()
        with mock.patch.object(Path, "read_text", return_value=guest["boot_id"]):
            self.assertEqual(guest, r.delivery(r.encoded(guest), r.sha(r.encoded(guest)), guest["recovery_id"], entry))
            for fault in ("long", "late", "wrong_id", "stop", "future", "renewed_prep", "spent_prep"):
                value = dict(guest)
                if fault == "long": value["deadline_ns"] += 1
                elif fault == "late": value["deadline_ns"] = entry["boottime_ns"]
                elif fault == "wrong_id": value["recovery_id"] = "other"
                elif fault == "stop": value["stop_ns"] += 1
                elif fault == "future": value["issued_ns"] = entry["boottime_ns"] + 1
                elif fault == "renewed_prep": value["preparation_deadline_ns"] = entry["boottime_ns"] + r.PREPARATION_NS
                else: value["preparation_deadline_ns"] = entry["boottime_ns"]
                with self.subTest(fault=fault), self.assertRaises(ValueError):
                    r.delivery(r.encoded(value), r.sha(r.encoded(value)), guest["recovery_id"], entry)

    def test_no_argument_entry_does_not_sample_platform_clock(self):
        with mock.patch.object(r, "first_clock", side_effect=AssertionError("platform clock used")) as clock, \
             mock.patch.object(r, "helper") as helper, mock.patch.object(sys, "stdout", new_callable=io.StringIO) as output:
            self.assertEqual(3, r.main([]))
        self.assertEqual("BLOCKED", json.loads(output.getvalue())["status"])
        clock.assert_not_called(); helper.assert_not_called()

    def test_explicit_nonlinux_execution_blocks_before_clock_or_helpers(self):
        argv = ["--execute"]
        for flag in ("plan", "sha256", "recovery", "recovery-sha256", "delivery-envelope", "delivery-sha256"):
            argv.extend(["--" + flag, "unused"])
        with mock.patch.object(r.sys, "platform", "win32"), \
             mock.patch.object(r, "first_clock", side_effect=AssertionError("platform clock used")) as clock, \
             mock.patch.object(r, "helper") as helper, mock.patch.object(sys, "stdout", new_callable=io.StringIO) as output:
            self.assertEqual(3, r.main(argv))
        self.assertEqual("RECOVERY_DRIVER_ISOLATED_ROOT_REQUIRED", json.loads(output.getvalue())["reason"])
        clock.assert_not_called(); helper.assert_not_called()

    def test_no_argument_entry_has_no_helper_or_filesystem_effect(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(PATH)], capture_output=True, timeout=10)
        self.assertEqual(3, result.returncode)
        self.assertEqual("BLOCKED", json.loads(result.stdout)["status"])
        self.assertEqual(b"", result.stderr)


if __name__ == "__main__":
    unittest.main()
