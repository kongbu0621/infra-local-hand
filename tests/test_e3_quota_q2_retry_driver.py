"""New-attempt authority and real assembly/SQLite over explicit modeled facts."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest("Linux retry assembly fixtures require Unix identity and ownership")

from test_e3_quota_q2_prepare_driver import fixture as original_fixture, ModelFiles
from test_e3_quota_q2_recovery_driver import ledger_command

PATH = Path(__file__).parent / "e3_host/q2_retry_driver.py"
spec = importlib.util.spec_from_file_location("q2_retry_driver_test", PATH)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def fixture():
    plan, old = original_fixture()
    plan["preparation_id"] = "retry001"
    plan["budgets"] = dict(state_bytes=32*1024**2, state_inodes=4096,
        capture_bytes=64*1024**2, capture_inodes=4096)
    retry = dict(schema="local-hand-q2-cpuquota-retry/v1", scope="LH-Q2-CPUQUOTA-RETRY-v1",
        baseline="d8e49617efecae199b0874f183530794f8c36e6a", closure="b0964e7adb50a49064f522fedbb1d46c3af08911",
        attempt_id=plan["preparation_id"], original_plan_sha256="a"*64,
        old_files={"/retained/prepared.json":"b"*64, "/retained/handoff.json":"c"*64},
        old_prepared="/retained/prepared.json", old_handoff="/retained/handoff.json",
        old_owner_output="/retained/owner_output", source=dict(commit="d"*40, tree="e"*40,
            files={"/new/tools.py":"f"*64}))
    observed = copy.deepcopy(old["facts"])
    # Existing live inventory contains the seven reused domains as well as Q1.
    observed["capacity_observed"]["quota_inventory"].extend(dict(project=root["project_id"],
        hard=root["hard_bytes"]//1024, ihard=root["inode_hard_limit"])
        for root in observed["roots"])
    attestation = dict(original_owner_issued=True, unused_roots=True, unused_ledger=True,
        roots=copy.deepcopy(observed["roots"]), old_prepared_sha256="b"*64,
        startup=dict(returncode=1, eof=["stderr", "stdout"], error="CPU quota '100.0000%' invalid."))
    receipt = dict(schema="local-hand-q2-cpuquota-retry-preparation/v1", status="RETRY_RESOURCES_PREPARED",
        fixture_generated=False, q2_accepted=False, q3_accepted=False, production_supported=False,
        attempt_id=retry["attempt_id"], retry_sha256=r.sha(r.encoded(retry)), plan_sha256=r.sha(r.encoded(plan)),
        facts=observed, retry=dict(directory=copy.deepcopy(observed["directories"]["reservation"]),
            attestation=attestation, attestation_sha256=r.sha(r.encoded(attestation)), original_files_preserved=True))
    entry = dict(monotonic_ns=50*10**9, boottime_ns=1000*10**9)
    guest = dict(schema=r.DELIVERY_SCHEMA, attempt_id=retry["attempt_id"], boot_id=observed["host"]["boot_id"],
        issued_ns=999*10**9, deadline_ns=1269*10**9, stop_ns=3*10**9,
        guest_outer_deadline_ns=1280*10**9, clock_anchor_sha256="e"*64, preparation_deadline_ns=1139*10**9)
    return plan, retry, receipt, entry, guest


def costs():
    return {role:dict(bytes=0, inodes=0) for role in ("state", "capture")}


def assemble(plan, retry, receipt, entry, guest, *, files=None, command=None,
        verify_preserved=lambda:None, measure_costs=costs, clock=None):
    files = ModelFiles() if files is None else files
    return r.complete(plan, retry, receipt, files=files,
        command=ledger_command(plan, files, []) if command is None else command,
        clock=clock or (lambda:dict(boot_id=guest["boot_id"], boottime_ns=1001*10**9)),
        entry=entry, delivery_envelope=guest, verify_preserved=verify_preserved,
        measure_costs=measure_costs, wall_clock=lambda:1800000000*10**9)


class RetryDriverTests(unittest.TestCase):
    def test_new_authority_links_issued_old_failure_and_actual_roots_without_modification(self):
        args = fixture(); plan, retry, receipt, entry, guest = args
        plan["settings"]["identity"]["expires_at"] = 1
        receipt["plan_sha256"] = r.sha(r.encoded(plan))
        before = [r.encoded(value) for value in (plan, retry, receipt)]
        files = ModelFiles(); calls = []; checks=[]
        prepared, invocation = assemble(*args, files=files,
            command=ledger_command(plan, files, calls), verify_preserved=lambda:checks.append(True))
        self.assertEqual("RETRY_PREPARED", prepared["status"])
        self.assertEqual(before, [r.encoded(value) for value in (plan, retry, receipt)])
        self.assertEqual(1,len(calls)); self.assertEqual([True, True],checks)
        handoff = files.writes[invocation[invocation.index("--plan")+1]][0]
        request = handoff["template"]["launcher"]["resident"]["request"]
        self.assertEqual(1800000120, request["expires_at"])
        self.assertEqual(prepared["request_digest"], request["request_digest"])
        authority = files.writes[receipt["retry"]["directory"]["path"]+"/authority.json"][0]
        self.assertTrue(authority["original_owner_issued"])
        self.assertTrue(authority["original_verdict_retained"])
        self.assertEqual("c"*64,authority["supersedes_failed_attempt"]["handoff_sha256"])
        self.assertEqual(receipt["retry"]["attestation_sha256"],
            authority["unused_root_operation_binding"]["attestation_sha256"])
        self.assertEqual(receipt["facts"]["roots"],authority["unused_root_operation_binding"]["roots"])
        self.assertNotIn("original_request_unissued",authority["new_request_issuance"])
        domains=handoff["template"]["launcher"]["assembly"]["installation"]["capacity"]["domains"]
        self.assertEqual(8,len(domains))
        self.assertEqual(len(domains),len({(item["filesystem_uuid"],item["project_id"]) for item in domains}))
        self.assertEqual(1,len([name for name in files.writes if name.endswith("new-request-issuance.json")]))
        self.assertTrue(invocation[3].endswith("/tests/e3_host/q2_prepare_run.py"))
        self.assertFalse(any(name.startswith("/retained/") for name in files.writes))
        with self.assertRaises(FileExistsError):
            assemble(*args, files=files, command=lambda _:self.fail("second ledger initialized"))

    def test_strict_new_contract_assembles_with_fixed_replacement_source_identity(self):
        from test_e3_quota_q2_retry_contract import fixture as contract_fixture, r as contract
        original, retry = contract_fixture()
        original["tools"]["setpriv"] = original_fixture()[0]["tools"]["setpriv"]
        retry["original_plan_sha256"] = retry["old_files"][retry["original_plan_path"]] = r.sha(r.encoded(original))
        plan = contract.bind(original, contract.decode(contract.encoded(retry), contract.sha(contract.encoded(retry))))
        _, _, receipt, entry, guest = fixture()
        observed = receipt["facts"]
        observed["host"] = copy.deepcopy(plan["host"])
        observed["ordinary"] = copy.deepcopy(plan["account"])
        observed["parents"]["ordinary"]["path"] = "/user.slice/user-1100.slice/user@1100.service/q2work.slice"
        observed["parents"]["ordinary"].update(uid=1100,gid=1100)
        for role, directory in plan["directories"].items():
            observed["directories"][role]["path"] = directory["path"]
            observed["directories"][role].update(uid=1100 if directory["owner"]=="ordinary" else 0,
                gid=1100 if directory["owner"]=="ordinary" else 0)
        for planned, measured in zip(plan["roots"], observed["roots"]):
            measured.update(planned,uid=1100,gid=1100,filesystem_uuid=plan["mounts"]["quota"]["uuid"])
        installation = observed["installation"]
        installation["source"].update(root=plan["candidate"]["destination"]+"/source",
            commit=plan["candidate"]["commit"],tree=plan["candidate"]["tree"])
        installation["installed"]["source_commit"] = plan["candidate"]["commit"]
        installation["admin"]["entry"]["path"] = installation["source"]["root"]+"/tools/admin/local_hand_quota_observer/q2_entry.py"
        observed["capacity_observed"]["quota_inventory"] = [dict(project=value["project_id"],
            hard=value["hard_bytes"]//1024,ihard=value["inode_hard_limit"])
            for value in plan["retained_domains"]+plan["roots"]]
        receipt.update(attempt_id=retry["attempt_id"],retry_sha256=r.sha(r.encoded(retry)),plan_sha256=r.sha(r.encoded(plan)))
        receipt["retry"]["directory"] = copy.deepcopy(observed["directories"]["reservation"])
        attestation=receipt["retry"]["attestation"]
        attestation.update(roots=copy.deepcopy(observed["roots"]),old_prepared_sha256=retry["old_files"][retry["old_prepared"]])
        receipt["retry"]["attestation_sha256"]=r.sha(r.encoded(attestation))
        guest["boot_id"]=plan["host"]["boot_id"]
        files=ModelFiles()
        prepared,invocation=assemble(plan,retry,receipt,entry,guest,files=files)
        envelope=files.writes[invocation[invocation.index("--plan")+1]][0]
        domains=envelope["template"]["launcher"]["assembly"]["installation"]["capacity"]["domains"]
        self.assertEqual(11,len(domains))
        self.assertEqual(203*1024**2,sum(domain["hard_bytes"] for domain in domains))
        self.assertEqual(contract.CANDIDATE_COMMIT,prepared["source_commit"])
        self.assertEqual(plan["candidate"]["destination"]+"/source/tests/e3_host/q2_prepare_run.py",invocation[3])

    def test_unknown_unused_proof_cannot_publish_children(self):
        for fault in ("status", "accepted", "plan", "retry", "preserved", "owner_unissued", "root_used",
                "ledger_used", "attestation", "root_pin", "prepared", "retained", "source"):
            args=fixture();plan,retry,receipt,entry,guest=args;files=ModelFiles()
            attestation=receipt["retry"]["attestation"]
            if fault=="status":receipt["status"]="INCOMPLETE"
            elif fault=="accepted":receipt["q2_accepted"]=True
            elif fault in ("plan","retry"):receipt[fault+"_sha256"]="0"*64
            elif fault=="preserved":receipt["retry"]["original_files_preserved"]=False
            elif fault=="owner_unissued":attestation["original_owner_issued"]=False
            elif fault=="root_used":attestation["unused_roots"]=False
            elif fault=="ledger_used":attestation["unused_ledger"]=False
            elif fault=="attestation":receipt["retry"]["attestation_sha256"]="0"*64
            elif fault=="root_pin":attestation["roots"][0]["inode"]+=1
            elif fault=="prepared":attestation["old_prepared_sha256"]="0"*64
            elif fault=="retained":receipt["facts"]["retained_after"]=[]
            else:receipt["facts"]["installation"]["source"]["commit"]="0"*40
            if fault!="attestation":receipt["retry"]["attestation_sha256"]=r.sha(r.encoded(attestation))
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                assemble(*args,files=files,command=lambda _:self.fail("ledger issued"))
            self.assertFalse(files.writes);self.assertFalse(files.dirs)

    def test_quota_adapter_rejects_missing_changed_or_duplicate_reused_domain(self):
        for fault in ("missing","hard","inodes","duplicate","unrelated_duplicate"):
            args=fixture();plan,retry,receipt,entry,guest=args;files=ModelFiles()
            inventory=receipt["facts"]["capacity_observed"]["quota_inventory"]
            if fault=="missing":inventory.pop()
            elif fault=="hard":inventory[-1]["hard"]+=1
            elif fault=="inodes":inventory[-1]["ihard"]+=1
            elif fault=="duplicate":inventory.append(copy.deepcopy(inventory[-1]))
            else:inventory.append(copy.deepcopy(inventory[0]))
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                assemble(*args,files=files,command=lambda _:self.fail("ledger issued"))
            self.assertFalse(files.writes);self.assertFalse(files.dirs)

    def test_time_already_consumed_does_not_issue_another_owner_deadline(self):
        args=fixture();files=ModelFiles();clocks=iter([1001,1002,1140])
        with self.assertRaisesRegex(ValueError,"PREPARATION_EXPIRED"):
            assemble(*args,files=files,clock=lambda:dict(boot_id=args[-1]["boot_id"],boottime_ns=next(clocks)*10**9))
        self.assertTrue(any(name.endswith("new-request-issuance.json") for name in files.writes))
        self.assertFalse(any(name.endswith("handoff.json") for name in files.writes))

    def test_old_evidence_drift_prevents_handoff_but_retains_new_assembly(self):
        args=fixture();files=ModelFiles()
        def changed():raise ValueError("OLD_EVIDENCE_CHANGED")
        with self.assertRaisesRegex(ValueError,"OLD_EVIDENCE_CHANGED"):
            assemble(*args,files=files,verify_preserved=changed)
        self.assertTrue(any(name.endswith("prepared.json") for name in files.writes))
        self.assertFalse(any(name.endswith("handoff.json") for name in files.writes))

    def test_all_reserved_assembly_space_is_charged_before_any_children(self):
        for role,key in (("state","bytes"),("state","inodes"),("capture","bytes"),("capture","inodes")):
            args=fixture();files=ModelFiles();measured=costs()
            measured[role][key]=args[0]["budgets"][role+"_"+key]
            with self.subTest(role=role,key=key),self.assertRaisesRegex(ValueError,"ASSEMBLY_CAPACITY"):
                assemble(*args,files=files,measure_costs=lambda:measured,command=lambda _:self.fail("ledger issued"))
            self.assertFalse(files.writes);self.assertFalse(files.dirs)

    def test_final_created_handoff_is_measured_before_exec_returned(self):
        args=fixture();files=ModelFiles();checks=[]
        def verify():
            checks.append(True)
            if len(checks)==2:
                self.assertTrue(any(name.endswith("handoff.json") for name in files.writes))
                raise ValueError("RETRY_TOTAL_CAPACITY")
        with self.assertRaisesRegex(ValueError,"RETRY_TOTAL_CAPACITY"):
            assemble(*args,files=files,verify_preserved=verify)
        self.assertEqual(2,len(checks))

    def test_os_failure_reports_bounded_errno_and_path_without_reading_file(self):
        error=PermissionError(13,"permission denied", "/private/"+"x"*2048)
        detail=r.error_details(error)
        self.assertEqual("PermissionError",detail["type"])
        self.assertEqual(13,detail["errno"])
        self.assertEqual(512,len(detail["filename"]))
        self.assertLessEqual(len(detail["message"]),1024)
        self.assertIsNone(r.error_details(ValueError("RETRY_DEADLINE")))
        self.assertLess(len(r.encoded(detail)),2048)

    def test_no_argument_entry_blocks_without_effects(self):
        result=subprocess.run([sys.executable,"-I","-B",str(PATH)],capture_output=True,timeout=10)
        self.assertEqual(3,result.returncode)
        self.assertEqual("BLOCKED",json.loads(result.stdout)["status"])
        self.assertEqual(b"",result.stderr)


if __name__=="__main__":unittest.main()
