"""Dual-predecessor authority and real assembly/SQLite over modeled guest facts."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

if sys.platform.startswith("linux"):
    from test_e3_quota_q2_prepare_driver import fixture as original_fixture, ModelFiles
    from test_e3_quota_q2_recovery_driver import ledger_command

PATH = Path(__file__).parent / "e3_host/q2_startup_retry_driver.py"
spec = importlib.util.spec_from_file_location("q2_startup_retry_driver_test", PATH)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def fixture():
    from test_e3_quota_q2_retry_driver import fixture as previous_fixture
    plan, previous, receipt, entry, guest = previous_fixture()
    plan["preparation_id"] = "startup001"
    plan["host"] = copy.deepcopy(receipt["facts"]["host"])
    plan["candidate"]["wheel_sha256"] = "1" * 64
    predecessors = []
    old_files = {}
    for index, kind in enumerate(("CPUQUOTA_PARSE_BEFORE_CHILD", "SUPERVISOR_STARTED_PERMISSION_FAILURE")):
        prefix = "/retained/attempt" + str(index)
        item = dict(kind=kind, plan_path=prefix + "/plan.json", plan_sha256=str(index + 2) * 64,
            prepared_path=prefix + "/prepared.json", handoff_path=prefix + "/handoff.json",
            owner_output=prefix + "/owner_output", policy_path=prefix + "/policy.json", failed_units=[],
            ledger=dict(path=prefix + "/jobs.sqlite", device=70, inode=200 + index, mode=0o600,
                uid=plan["account"]["uid"], ledger_id="old-ledger-" + str(index), generation=[1, 1]))
        for path in (item["plan_path"], item["prepared_path"], item["handoff_path"],
                     item["policy_path"], item["ledger"]["path"]):
            old_files[path] = str(index + 2) * 64
        predecessors.append(item)
    retry = dict(schema="local-hand-q2-supervisor-startup-retry/v1", scope="LH-Q2-SUPERVISOR-STARTUP-RETRY-v1",
        rule="10d2a5c827964989f41ca6e8eeac3d44de6d0f04", baseline="47b351b2b943bf1d6f1c71cfeb031157a2eb70cc",
        closure="d4a925c883672fadc7d1b10a8dfe58df18b922cd", owner_decision="LH-Q2-SUPERVISOR-STARTUP-RETRY-CLOSURE-20260927-01",
        attempt_id=plan["preparation_id"], original_plan_sha256="a" * 64, original_plan_path="/retained/original-plan.json",
        predecessors=predecessors, old_files=old_files, reservations=[dict(path=item["owner_output"] + "/reservation.json",
            category="capture", covered_paths=[item["owner_output"]]) for item in predecessors],
        source=previous["source"], candidate=copy.deepcopy(plan["candidate"]))
    bindings = r.predecessor_bindings(retry)
    attestation = dict(original_files_preserved=True, unused_roots=True, unused_ledgers=True,
        roots=copy.deepcopy(receipt["facts"]["roots"]), predecessors=[dict(
            {key: item[key] for key in ("kind", "plan_sha256", "prepared_sha256", "handoff_sha256", "owner_output")},
            original_owner_issued=True, original_status="INCOMPLETE") for item in bindings],
        ledgers=[dict(item["ledger"], authority_id="old-authority", unused=True) for item in bindings])
    receipt.update(schema="local-hand-q2-supervisor-startup-retry-preparation/v1",
        status="STARTUP_RETRY_RESOURCES_PREPARED", attempt_id=retry["attempt_id"],
        retry_sha256=r.sha(r.encoded(retry)), plan_sha256=r.sha(r.encoded(plan)))
    receipt["retry"].update(attestation=attestation, attestation_sha256=r.sha(r.encoded(attestation)))
    guest.update(schema=r.DELIVERY_SCHEMA, attempt_id=retry["attempt_id"])
    receipt.update(delivery_envelope=copy.deepcopy(guest), delivery_sha256=r.sha(r.encoded(guest)),
                   clock_anchor_sha256=guest["clock_anchor_sha256"])
    return plan, retry, receipt, entry, guest


def costs():
    return {role: dict(bytes=0, inodes=0) for role in ("state", "capture")}


def strict_fixture():
    """Real three-plan decoder, with installation and host observations modeled."""
    from test_e3_q2_startup_retry_contract import fixture as contract_fixture, r as contract
    original, previous, retry = contract_fixture()
    original["tools"]["setpriv"] = original_fixture()[0]["tools"]["setpriv"]
    original_sha = r.sha(r.encoded(original))
    previous["original_plan_sha256"] = previous["old_files"][previous["original_plan_path"]] = original_sha
    retry["original_plan_sha256"] = retry["predecessors"][0]["plan_sha256"] = original_sha
    retry["old_files"][retry["original_plan_path"]] = original_sha
    retry["old_files"][original["directories"]["reservation"]["path"] + "/intent.json"] = original_sha
    previous_sha = r.sha(r.encoded(previous))
    retry["predecessors"][1]["plan_sha256"] = previous_sha
    retry["old_files"][retry["predecessors"][1]["plan_path"]] = previous_sha
    plan = contract.bind(original, contract.decode(contract.encoded(retry), contract.sha(contract.encoded(retry))), previous)
    _, _, receipt, entry, guest = fixture()
    observed = receipt["facts"]
    observed["host"] = copy.deepcopy(plan["host"])
    observed["ordinary"] = copy.deepcopy(plan["account"])
    uid = plan["account"]["uid"]; gid = plan["account"]["gid"]
    observed["parents"]["ordinary"].update(uid=uid, gid=gid,
        path=f"/user.slice/user-{uid}.slice/user@{uid}.service/q2work.slice")
    for role, directory in plan["directories"].items():
        observed["directories"][role]["path"] = directory["path"]
        observed["directories"][role].update(uid=uid if directory["owner"] == "ordinary" else 0,
            gid=gid if directory["owner"] == "ordinary" else 0)
    for planned, measured in zip(plan["roots"], observed["roots"]):
        measured.update(planned, uid=uid, gid=gid, filesystem_uuid=plan["mounts"]["quota"]["uuid"])
    installation = observed["installation"]
    installation["source"].update(root=plan["candidate"]["destination"] + "/source",
        commit=plan["candidate"]["commit"], tree=plan["candidate"]["tree"])
    installation["installed"]["source_commit"] = plan["candidate"]["commit"]
    installation["admin"]["entry"]["path"] = installation["source"]["root"] + "/tools/admin/local_hand_quota_observer/q2_entry.py"
    observed["capacity_observed"]["quota_inventory"] = [dict(project=value["project_id"],
        hard=value["hard_bytes"] // 1024, ihard=value["inode_hard_limit"])
        for value in plan["retained_domains"] + plan["roots"]]
    receipt.update(attempt_id=retry["attempt_id"], retry_sha256=r.sha(r.encoded(retry)), plan_sha256=r.sha(r.encoded(plan)))
    receipt["retry"]["directory"] = copy.deepcopy(observed["directories"]["reservation"])
    bindings = r.predecessor_bindings(retry)
    attestation = receipt["retry"]["attestation"]
    attestation.update(roots=copy.deepcopy(observed["roots"]), predecessors=[dict(
        {key: item[key] for key in ("kind", "plan_sha256", "prepared_sha256", "handoff_sha256", "owner_output")},
        original_owner_issued=True, original_status="INCOMPLETE") for item in bindings],
        ledgers=[dict(item["ledger"], authority_id="modeled-historical-authority", unused=True) for item in bindings])
    receipt["retry"]["attestation_sha256"] = r.sha(r.encoded(attestation))
    guest.update(boot_id=plan["host"]["boot_id"], attempt_id=retry["attempt_id"])
    receipt.update(delivery_envelope=copy.deepcopy(guest), delivery_sha256=r.sha(r.encoded(guest)))
    return plan, retry, receipt, entry, guest


def assemble(plan, retry, receipt, entry, guest, *, files=None, command=None,
             verify_preserved=lambda: None, measure_costs=costs, clock=None):
    files = ModelFiles() if files is None else files
    return r.complete(plan, retry, receipt, files=files,
        command=ledger_command(plan, files, []) if command is None else command,
        clock=clock or (lambda: dict(boot_id=guest["boot_id"], boottime_ns=1001 * 10**9)),
        entry=entry, delivery_envelope=guest, verify_preserved=verify_preserved,
        measure_costs=measure_costs, wall_clock=lambda: 1800000000 * 10**9)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux assembly and inherited ownership fixtures")
class StartupRetryDriverTests(unittest.TestCase):
    def test_strict_contract_assembles_frozen_candidate_and_all_ten_reservations(self):
        args = strict_fixture(); plan, retry, receipt, entry, guest = args; files = ModelFiles()
        prepared, invocation = assemble(*args, files=files)
        self.assertEqual("b49d3df3d1e76813faf08e59ab4975e25279c2fc", prepared["source_commit"])
        self.assertEqual("c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b",
                         prepared["runtime_candidate"]["wheel_sha256"])
        authority = files.writes[receipt["retry"]["directory"]["path"] + "/authority.json"][0]
        self.assertEqual(retry["reservations"], authority["reservations"])
        self.assertEqual(10, len(authority["reservations"]))
        self.assertEqual(retry["predecessors"], authority["predecessors"])
        self.assertEqual(plan["candidate"]["destination"] + "/source/tests/e3_host/q2_prepare_run.py", invocation[3])
        handoff = files.writes[invocation[invocation.index("--plan") + 1]][0]
        domains = handoff["template"]["launcher"]["assembly"]["installation"]["capacity"]["domains"]
        self.assertEqual(11, len(domains))
        self.assertEqual(203 * 1024**2, sum(domain["hard_bytes"] for domain in domains))

    def test_real_assembly_and_ledger_bind_both_predecessors_and_fresh_exec(self):
        args = fixture(); plan, retry, receipt, entry, guest = args
        before = [r.encoded(value) for value in (plan, retry, receipt)]
        files = ModelFiles(); calls = []; checks = []
        prepared, invocation = assemble(*args, files=files, command=ledger_command(plan, files, calls),
            verify_preserved=lambda: checks.append(True))
        self.assertEqual("STARTUP_RETRY_PREPARED", prepared["status"])
        self.assertEqual(r.sha(r.encoded(guest)), prepared["delivery_sha256"])
        self.assertEqual(guest["clock_anchor_sha256"], prepared["clock_anchor_sha256"])
        self.assertEqual(before, [r.encoded(value) for value in (plan, retry, receipt)])
        self.assertEqual(1, len(calls)); self.assertEqual(3, len(checks))
        self.assertTrue(prepared["original_owners_issued"] and prepared["original_verdicts_retained"])
        self.assertEqual(r.predecessor_bindings(retry), prepared["supersedes_failed_attempt"])
        authority = files.writes[receipt["retry"]["directory"]["path"] + "/authority.json"][0]
        for key in ("rule", "baseline", "closure", "owner_decision", "predecessors", "reservations"):
            self.assertEqual(retry[key], authority[key])
        self.assertEqual(r.sha(r.encoded(retry["old_files"])), authority["original_files_sha256"])
        self.assertEqual(2, len(authority["ledger_attestations"]))
        self.assertEqual(receipt["facts"]["roots"], authority["unused_root_operation_binding"]["roots"])
        handoff = files.writes[invocation[invocation.index("--plan") + 1]][0]
        request = handoff["template"]["launcher"]["resident"]["request"]
        self.assertEqual(prepared["request_digest"], request["request_digest"])
        self.assertEqual(1800000120, request["expires_at"])
        self.assertEqual([item["handoff_sha256"] for item in r.predecessor_bindings(retry)],
            authority["new_request_issuance"]["supersedes_handoff_sha256"])
        self.assertEqual(["-I", "-B"], invocation[1:3])
        self.assertTrue(invocation[3].endswith("/source/tests/e3_host/q2_prepare_run.py"))
        self.assertFalse(any(name.startswith("/retained/") for name in files.writes))
        domains = handoff["template"]["launcher"]["assembly"]["installation"]["capacity"]["domains"]
        self.assertEqual(len(domains), len({(item["filesystem_uuid"], item["project_id"]) for item in domains}))
        with self.assertRaises(FileExistsError):
            assemble(*args, files=files, command=lambda _: self.fail("ledger replay"))

    def test_each_dual_predecessor_and_ledger_claim_is_required_before_mutation(self):
        for fault in ("missing_predecessor", "order", "first_unissued", "second_complete", "first_handoff",
                      "second_plan", "second_ledger", "second_used", "roots", "preserved", "receipt", "host", "window",
                      "old_schema", "accepted", "single_ledger", "ledger_digest", "source", "boot"):
            args = fixture(); plan, retry, receipt, entry, guest = args; files = ModelFiles()
            attestation = receipt["retry"]["attestation"]
            if fault == "missing_predecessor": attestation["predecessors"].pop()
            elif fault == "order": attestation["predecessors"].reverse()
            elif fault == "first_unissued": attestation["predecessors"][0]["original_owner_issued"] = False
            elif fault == "second_complete": attestation["predecessors"][1]["original_status"] = "COMPLETE"
            elif fault == "first_handoff": attestation["predecessors"][0]["handoff_sha256"] = "0" * 64
            elif fault == "second_plan": attestation["predecessors"][1]["plan_sha256"] = "0" * 64
            elif fault == "second_ledger": attestation["ledgers"][1]["inode"] += 1
            elif fault == "second_used": attestation["ledgers"][1]["unused"] = False
            elif fault == "roots": attestation["roots"][0]["inode"] += 1
            elif fault == "preserved": receipt["retry"]["original_files_preserved"] = False
            elif fault == "receipt": receipt["plan_sha256"] = "0" * 64
            elif fault == "host": receipt["facts"]["host"]["initial_userns"]["inode"] += 1
            elif fault == "old_schema": receipt["schema"] = "local-hand-q2-cpuquota-retry-preparation/v1"
            elif fault == "accepted": receipt["q2_accepted"] = True
            elif fault == "single_ledger": attestation["ledgers"].pop()
            elif fault == "ledger_digest": attestation["ledgers"][1]["sha256"] = "0" * 64
            elif fault == "source": receipt["facts"]["installation"]["source"]["commit"] = "0" * 40
            elif fault == "boot": receipt["facts"]["host"]["boot_id"] = "0" * 36
            else: receipt["delivery_envelope"]["deadline_ns"] += 1
            receipt["retry"]["attestation_sha256"] = r.sha(r.encoded(attestation))
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                assemble(*args, files=files, command=lambda _: self.fail("ledger issued"))
            self.assertFalse(files.writes); self.assertFalse(files.dirs)

    def test_cumulative_capacity_and_first_preservation_check_precede_children(self):
        for role, key in (("state", "bytes"), ("state", "inodes"), ("capture", "bytes"), ("capture", "inodes")):
            args = fixture(); files = ModelFiles(); measured = costs()
            measured[role][key] = args[0]["budgets"][role + "_" + key]
            with self.subTest(role=role, key=key), self.assertRaisesRegex(ValueError, "ASSEMBLY_CAPACITY"):
                assemble(*args, files=files, measure_costs=lambda: measured)
            self.assertFalse(files.writes); self.assertFalse(files.dirs)
        args = fixture(); files = ModelFiles()
        with self.assertRaisesRegex(ValueError, "OLD_EVIDENCE_CHANGED"):
            assemble(*args, files=files, verify_preserved=lambda: (_ for _ in ()).throw(ValueError("OLD_EVIDENCE_CHANGED")))
        self.assertFalse(files.writes); self.assertFalse(files.dirs)

    def test_second_and_final_preservation_failure_never_return_an_exec(self):
        for fail_at in (2, 3):
            args = fixture(); files = ModelFiles(); checks = []
            def verify():
                checks.append(True)
                if len(checks) == fail_at: raise ValueError("HISTORY_CHANGED")
            with self.subTest(fail_at=fail_at), self.assertRaisesRegex(ValueError, "HISTORY_CHANGED"):
                assemble(*args, files=files, verify_preserved=verify)
            self.assertTrue(any(path.endswith("prepared.json") for path in files.writes))
            self.assertEqual(fail_at == 3, any(path.endswith("handoff.json") for path in files.writes))

    def test_expired_preparation_cannot_issue_a_fresh_owner_window(self):
        args = fixture(); files = ModelFiles(); clocks = iter([1001, 1002, 1140])
        with self.assertRaisesRegex(ValueError, "PREPARATION_EXPIRED"):
            assemble(*args, files=files, clock=lambda: dict(boot_id=args[-1]["boot_id"], boottime_ns=next(clocks) * 10**9))
        self.assertFalse(any(path.endswith("handoff.json") for path in files.writes))

    def test_main_reads_both_prior_plans_without_atime_and_execs_once_in_same_process(self):
        import contextlib

        plan, retry, receipt, entry, guest = fixture()
        original, previous = {"original": True}, {"previous": True}
        invocation = ["/frozen/python", "-I", "-B", "/frozen/source/tests/e3_host/q2_prepare_run.py",
                      "--plan", "/new/handoff.json", "--sha256", "e" * 64]
        backend = mock.Mock(reservation=None)
        backend.prepare.return_value = receipt
        backend.guard = lambda: None
        factory = mock.Mock(return_value=backend)
        protected = SimpleNamespace(read=mock.Mock(return_value=b"protected bytes"))
        contract = SimpleNamespace(decode=mock.Mock(return_value=retry), bind=mock.Mock(return_value=plan))
        delivery = mock.Mock()
        delivery.validate_delivery.return_value = guest
        delivery.preparation_window.return_value = (entry["monotonic_ns"], entry["monotonic_ns"] + 10**9)
        delivery.preparation_guard.side_effect = lambda guard, *unused: guard
        prepare_driver = SimpleNamespace(validate_plan=lambda _: plan["settings"], Files=mock.Mock())
        helpers = {"q2_prepare": protected, "q2_startup_retry_contract": contract,
            "q2_startup_retry_delivery": delivery, "q2_prepare_contract": SimpleNamespace(decode=mock.Mock(return_value=original)),
            "q2_retry_contract": SimpleNamespace(decode=mock.Mock(return_value=previous)),
            "q2_prepare_driver": prepare_driver, "q2_startup_retry": SimpleNamespace(StartupRetryBackend=factory)}
        class SamePidExec(BaseException): pass
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(r, "helper", side_effect=helpers.__getitem__))
            stack.enter_context(mock.patch.object(r, "first_clock", return_value=entry))
            stack.enter_context(mock.patch.object(r, "current_clock", return_value=dict(boot_id=guest["boot_id"], boottime_ns=1001*10**9)))
            stack.enter_context(mock.patch.object(r.sys, "flags", SimpleNamespace(isolated=1)))
            stack.enter_context(mock.patch.object(r.sys, "dont_write_bytecode", True))
            stack.enter_context(mock.patch.object(r.sys, "path", list(sys.path)))
            for name in ("getuid", "geteuid"): stack.enter_context(mock.patch.object(r.os, name, return_value=0))
            stack.enter_context(mock.patch.object(r, "complete", return_value=({"status": "STARTUP_RETRY_PREPARED"}, invocation)))
            execute = stack.enter_context(mock.patch.object(r.os, "execv", side_effect=SamePidExec))
            stack.enter_context(mock.patch("builtins.print"))
            with self.assertRaises(SamePidExec):
                r.main(["--retry", "/new/retry.json", "--sha256", "d"*64,
                        "--delivery-envelope", "/new/delivery.json", "--delivery-sha256", "f"*64, "--execute"])
        contract.bind.assert_called_once_with(original, retry, previous)
        self.assertEqual(["/new/retry.json", retry["original_plan_path"], retry["predecessors"][1]["plan_path"],
                          "/new/delivery.json"], [call.args[0] for call in protected.read.call_args_list])
        for call in protected.read.call_args_list: self.assertEqual({"noatime": True}, call.kwargs)
        backend.preflight.assert_called_once_with(); backend.reserve.assert_called_once_with(); backend.prepare.assert_called_once_with()
        execute.assert_called_once_with(invocation[0], invocation)



class StartupRetryEntryTests(unittest.TestCase):
    def test_nonlinux_execution_blocks_before_helper_import_or_host_read(self):
        with mock.patch.object(r.sys, "platform", "win32"), \
             mock.patch.object(r, "helper", side_effect=AssertionError("helper import")) as helper, \
             mock.patch("builtins.print") as output:
            self.assertEqual(3, r.main(["--retry", "/synthetic/retry", "--sha256", "a"*64,
                "--delivery-envelope", "/synthetic/envelope", "--delivery-sha256", "b"*64, "--execute"]))
        helper.assert_not_called()
        self.assertEqual("STARTUP_RETRY_DRIVER_ISOLATED_ROOT_REQUIRED", json.loads(output.call_args.args[0])["reason"])

    def test_os_diagnostic_contains_only_bounded_type_and_errno(self):
        error = PermissionError(13, "private message" * 10000, "/private/file")
        self.assertEqual(dict(type="PermissionError", errno=13), r.error_details(error))
        self.assertEqual(dict(type="OSError", errno=None), r.error_details(OSError(99999, "secret")))
        self.assertIsNone(r.error_details(ValueError("SCOPE")))

    def test_no_argument_entry_blocks_without_effects(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(PATH)], capture_output=True, timeout=10)
        self.assertEqual(3, result.returncode)
        value = json.loads(result.stdout)
        self.assertEqual("BLOCKED", value["status"])
        self.assertEqual("EXPLICIT_STARTUP_RETRY_AND_DELIVERY_REQUIRED", value["reason"])
        self.assertEqual(b"", result.stderr)


if __name__ == "__main__": unittest.main()
