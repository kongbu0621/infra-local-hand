"""Known-failure recovery proofs; no accounts, quotas or services are changed."""
import copy
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from test_e3_quota_q2_prepare_contract import fixture

PATH=Path(__file__).parent/"e3_host/q2_prepare_recovery.py"
spec=importlib.util.spec_from_file_location("_recovery_test",PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def original(plan):
    account=plan["account"]
    group=[plan["tools"]["groupadd"]["path"],"--gid",str(account["gid"]),account["name"]]
    user=[plan["tools"]["useradd"]["path"],"--uid",str(account["uid"]),"--gid",str(account["gid"]),
          "--no-user-group","--no-log-init","-K","CREATE_MAIL_SPOOL=no","--no-create-home",
          "--home-dir",plan["directories"]["state"]["path"],"--shell","/usr/sbin/nologin","--password","!",account["name"]]
    facts=dict(host=plan["host"],mounts={},retained_before=[{"synthetic":True}],capacity_observed={})
    receipt=dict(schema=m.p.SCHEMA,status="INCOMPLETE",reason="PREPARE_COMMAND_FAILED",
        preparation_id=plan["preparation_id"],plan_sha256=m.sha(m.c.encoded(plan)),facts=facts,
        q2_accepted=False,q3_accepted=False,production_supported=False,fixture_generated=False)
    values={"intent.json":plan,"preparation-result.json":receipt,"preflight.json":facts,
        "0001-step-intent.json":{"step":"ordinary"},"0002-command-intent.json":{"argv":group},
        "0003-command-result.json":dict(argv=group,returncode=0,eof=["stderr","stdout"],failure=None,stdout="",stderr=""),
        "0004-command-intent.json":{"argv":user},
        "0005-command-result.json":dict(argv=user,returncode=3,eof=["stderr","stdout"],failure=None,stdout="",stderr=m.ERROR.hex())}
    return {name:m.c.encoded(value) for name,value in values.items()}


def recovery_fixture(plan=None):
    plan=fixture() if plan is None else plan
    raw=original(plan)
    files={"/synthetic/tools/"+name+".py":"c"*64 for name in
           ("q2_prepare_recovery","q2_prepare","q2_prepare_contract","q2_prepare_build")}
    value=dict(schema=m.SCHEMA,purpose="KNOWN_ACCOUNT_PARSE_FAILURE",scope=m.SCOPE,baseline=m.BASELINE,
        recovery_id="recover001",preparation_id=plan["preparation_id"],plan_sha256=m.sha(m.c.encoded(plan)),
        reservation=dict(path=plan["directories"]["reservation"]["path"],device=11,inode=7,uid=0,gid=0,mode=stat.S_IFDIR|0o700),
        staged_plan="/synthetic/input/plan.json",original_files={name:m.sha(raw[name]) for name in m.PINNED_FILES},
        original_service="lhqfixture001.service",
        original_capture=dict(report_sha256="d"*64,stdout_sha256="e"*64,stderr_sha256="f"*64,
            receipt_sha256=m.sha(raw["preparation-result.json"]),returncode=3,eof=["stderr","stdout"],failure=None),
        recovery_source=dict(commit="a"*40,tree="b"*40,files=files),
        retained_inputs=[dict(path="/synthetic/input",category="installation"),dict(path="/synthetic/tools",category="installation")])
    return plan,value,raw


def backend():
    plan,recovery,_=recovery_fixture()
    issued=time.monotonic_ns()
    return m.RecoveryBackend(plan,recovery,issued,issued+140*10**9)


class ContractAndOriginalProof(unittest.TestCase):
    def test_exact_original_failure_is_supported_without_rewriting_verdict(self):
        plan,recovery,raw=recovery_fixture()
        self.assertEqual(recovery,m.bind_plan(plan,recovery))
        self.assertEqual("INCOMPLETE",m.verify_records(plan,recovery,raw)["status"])

    def test_invalid_scope_types_capture_and_extra_keys_rejected(self):
        _,value,_=recovery_fixture()
        for mutation in (lambda r:r.update(extra=True),lambda r:r.update(scope="OTHER"),
                         lambda r:r["reservation"].update(uid=False),
                         lambda r:r["original_capture"].update(returncode=True),
                         lambda r:r["original_capture"].update(eof=["stdout"]),
                         lambda r:r["original_capture"].update(failure="TIMEOUT")):
            changed=copy.deepcopy(value);mutation(changed);raw=m.c.encoded(changed)
            with self.subTest(value=changed),self.assertRaises(ValueError):m.decode(raw,m.sha(raw))

    def test_changed_original_and_unaccounted_or_overlapping_staging_rejected(self):
        plan,value,_=recovery_fixture()
        for mutation in (lambda r:r.update(plan_sha256="0"*64),
                         lambda r:r["retained_inputs"].pop(),
                         lambda r:r["retained_inputs"].append(dict(path="/synthetic/input/source",category="installation")),
                         lambda r:r["retained_inputs"].append(dict(path="/synthetic/old",category="state"))):
            changed=copy.deepcopy(value);mutation(changed)
            with self.subTest(value=changed),self.assertRaises(ValueError):m.bind_plan(plan,changed)

    def test_even_newly_pinned_unsupported_command_outcomes_cannot_resume(self):
        plan,value,raw=recovery_fixture()
        for name,changes in (("0003-command-result.json",{"returncode":1}),
                             ("0005-command-result.json",{"returncode":0}),
                             ("0005-command-result.json",{"stderr":b"other error".hex()}),
                             ("0005-command-result.json",{"stdout":b"changed".hex()}),
                             ("0005-command-result.json",{"eof":["stdout"]}),
                             ("0005-command-result.json",{"failure":"TIMEOUT"}),
                             ("0001-step-intent.json",{"step":"directories"})):
            changed=copy.deepcopy(raw);record=m.c.document(changed[name]);record.update(changes)
            changed[name]=m.c.encoded(record);pins=copy.deepcopy(value);pins["original_files"][name]=m.sha(changed[name])
            with self.subTest(name=name,changes=changes),self.assertRaisesRegex(ValueError,"RECOVERY_UNSUPPORTED_BOUNDARY"):
                m.verify_records(plan,pins,changed)

    def test_hidden_delivery_record_and_noncanonical_preflight_fail(self):
        plan,value,raw=recovery_fixture()
        changed=dict(raw,**{"0006-step-intent.json":b"{}\n"})
        with self.assertRaisesRegex(ValueError,"RECOVERY_ORIGINAL_MEMBERS"):m.verify_records(plan,value,changed)
        raw["preflight.json"]+=b" "
        with self.assertRaisesRegex(ValueError,"RECOVERY_PREFLIGHT_CHANGED"):m.verify_records(plan,value,raw)


class AccountAndClock(unittest.TestCase):
    def test_only_corrected_useradd_is_issued_once(self):
        b=backend();b.check_account_boundary=mock.Mock();b.verify_account=mock.Mock(return_value=b.plan["account"])
        b.command=mock.Mock(return_value=b"")
        with mock.patch.object(m,"read",return_value=b""),mock.patch.object(m.os.path,"lexists",return_value=False):
            self.assertEqual(b.plan["account"],b.account())
        b.command.assert_called_once();argv=b.command.call_args.args[0]
        self.assertEqual(b.tool("useradd"),argv[0]);self.assertIn("--system",argv);self.assertNotIn("-K",argv)
        self.assertNotIn(b.tool("groupadd"),argv);self.assertIn("--no-create-home",argv)

    def test_creation_failure_is_not_retried(self):
        b=backend();b.check_account_boundary=mock.Mock();b.verify_account=mock.Mock()
        b.command=mock.Mock(side_effect=ValueError("PREPARE_COMMAND_FAILED"))
        with self.assertRaisesRegex(ValueError,"PREPARE_COMMAND_FAILED"):b.account()
        b.command.assert_called_once();b.verify_account.assert_not_called()

    def test_reappeared_account_or_changed_group_blocks_before_useradd(self):
        import pwd,grp
        b=backend();a=b.plan["account"]
        with mock.patch.object(pwd,"getpwnam",return_value=object()):
            with self.assertRaisesRegex(ValueError,"RECOVERY_ACCOUNT_EXISTS"):b.check_account_boundary()
        wrong=grp.struct_group((a["name"],"x",a["gid"],["other"]))
        with mock.patch.object(pwd,"getpwnam",side_effect=KeyError),mock.patch.object(pwd,"getpwuid",side_effect=KeyError),\
             mock.patch.object(grp,"getgrnam",return_value=wrong),mock.patch.object(grp,"getgrgid",return_value=wrong):
            with self.assertRaisesRegex(ValueError,"RECOVERY_GROUP_CHANGED"):b.check_account_boundary()

    def test_missing_group_and_account_side_effects_cannot_be_reused(self):
        import pwd,grp
        b=backend();a=b.plan["account"]
        expected=grp.struct_group((a["name"],"x",a["gid"],[]))
        with mock.patch.object(pwd,"getpwnam",side_effect=KeyError),mock.patch.object(pwd,"getpwuid",side_effect=KeyError),\
             mock.patch.object(grp,"getgrnam",side_effect=KeyError):
            with self.assertRaisesRegex(ValueError,"RECOVERY_GROUP_CHANGED"):b.check_account_boundary()
        for name in ("/etc/shadow","/etc/subuid","/etc/subgid"):
            with self.subTest(name=name),mock.patch.object(pwd,"getpwnam",side_effect=KeyError),\
                 mock.patch.object(pwd,"getpwuid",side_effect=KeyError),\
                 mock.patch.object(grp,"getgrnam",return_value=expected),mock.patch.object(grp,"getgrgid",return_value=expected),\
                 mock.patch.object(m,"read",side_effect=lambda path,*args,**kwargs:(a["name"]+":1:1\n").encode() if path==name else b""):
                with self.assertRaisesRegex(ValueError,"RECOVERY_ACCOUNT_SIDE_EFFECT"):b.check_account_boundary()

    def test_absolute_deadline_is_never_refreshed(self):
        plan,recovery,_=recovery_fixture()
        with mock.patch.object(m.time,"monotonic_ns",return_value=100):
            b=m.RecoveryBackend(plan,recovery,99,199)
        with mock.patch.object(m.time,"monotonic_ns",return_value=200):
            with self.assertRaisesRegex(ValueError,"RECOVERY_DEADLINE"):b.guard()
            with self.assertRaisesRegex(ValueError,"RECOVERY_DEADLINE"):m.RecoveryBackend(plan,recovery,99,199)
        self.assertEqual(199,b.deadline)

    def test_inventory_cannot_certify_an_observation_that_finishes_after_deadline(self):
        b=backend()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"file";path.write_bytes(b"retained")
            with mock.patch.object(m.time,"monotonic_ns",side_effect=[b.deadline-1,b.deadline]):
                with self.assertRaisesRegex(ValueError,"RECOVERY_DEADLINE"):b.inventory(path)


class NeverIssuedRun(unittest.TestCase):
    def instance(self):
        b=backend()
        b.plan["settings"]["controllers"]={"management":{"unit":"lhqmanagement.service"},
                                            "supervisor":{"unit":"lhqsupervisor.service"}}
        return b

    def test_exited_original_service_and_absent_unissued_units_are_read_only(self):
        b=self.instance();old=b.recovery["original_service"]
        show=b"LoadState=loaded\nActiveState=failed\nSubState=failed\nMainPID=0\nControlPID=0\nJob=\n"
        b.command=mock.Mock(side_effect=[(old+" loaded failed failed original\n").encode(),b"",show])
        with mock.patch.object(m.os.path,"lexists",return_value=False):b.original_service_stopped()
        self.assertEqual(3,b.command.call_count)
        self.assertTrue(all(call.args[0][2] in ("list-units","list-jobs","show") for call in b.command.call_args_list))

    def test_loaded_queued_or_configured_future_unit_blocks(self):
        for units,jobs,configured in ((b"lhqsupervisor.service loaded inactive dead existing\n",b"",False),
                                      (b"",b"17 lhqmanagement.service start waiting\n",False),
                                      (b"",b"",True)):
            b=self.instance();b.command=mock.Mock(side_effect=[units,jobs])
            with self.subTest(units=units,jobs=jobs,configured=configured),\
                 mock.patch.object(m.os.path,"lexists",return_value=configured):
                with self.assertRaisesRegex(ValueError,"RECOVERY_RUN_ALREADY_ISSUED"):b.original_service_stopped()
            self.assertEqual(2,b.command.call_count)

    def test_original_job_or_live_pid_blocks_even_when_other_fields_look_stopped(self):
        for queued in (True,False):
            b=self.instance();old=b.recovery["original_service"]
            values=[(old+" loaded failed failed original\n").encode(),(b"19 "+old.encode()+b" stop running\n") if queued else b""]
            if not queued:values.append(b"LoadState=loaded\nActiveState=failed\nSubState=failed\nMainPID=123\nControlPID=0\nJob=\n")
            b.command=mock.Mock(side_effect=values)
            with self.subTest(queued=queued),mock.patch.object(m.os.path,"lexists",return_value=False):
                with self.assertRaisesRegex(ValueError,"RECOVERY_ORIGINAL_SERVICE_ACTIVE"):b.original_service_stopped()


class RetainedFilesAndBudgets(unittest.TestCase):
    def test_actual_original_directory_pin_and_extra_member_checked(self):
        b=backend()
        with tempfile.TemporaryDirectory() as td:
            directory=Path(td)/"original";directory.mkdir(mode=0o700)
            b.original_directory=directory;b.recovery["reservation"]=m.p.identity(directory.stat(),str(directory))
            for name in m.ORIGINAL_FILES:(directory/name).write_bytes(b"{}\n")
            with mock.patch.object(m.p,"opened",side_effect=lambda path,**_:os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)):
                b.original_members()
                (directory/"run-issued.json").write_bytes(b"{}\n")
                with self.assertRaisesRegex(ValueError,"RECOVERY_ORIGINAL_MEMBERS"):b.original_members()
                (directory/"run-issued.json").unlink();b.recovery["reservation"]["inode"]+=1
                with self.assertRaisesRegex(ValueError,"RECOVERY_RESERVATION_CHANGED"):b.original_members()

    def test_old_and_new_installation_inputs_share_original_budget(self):
        b=backend()
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);old=base/"old-stage";new=base/"recovery-stage";reservation=base/"reservation"
            for path in (old,new,reservation):path.mkdir()
            (old/"payload").write_bytes(b"a"*8192);(new/"payload").write_bytes(b"b"*8192)
            b.original_directory=reservation
            b.recovery["retained_inputs"]=[dict(path=str(old),category="installation"),dict(path=str(new),category="installation")]
            costs=b.measure_costs()
            self.assertEqual(b.inventory(old)["bytes"]+b.inventory(new)["bytes"],costs["installation"]["bytes"])
            self.assertEqual(1,costs["state"]["inodes"])
            b.plan["budgets"]["installation_bytes"]=costs["installation"]["bytes"]-1
            with self.assertRaisesRegex(ValueError,"RECOVERY_TOTAL_CAPACITY"):b.measure_costs()

    def test_inventory_rejects_symlinks_and_hardlinks_without_following(self):
        b=backend()
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);(base/"file").write_bytes(b"original");(base/"link").symlink_to(base/"file")
            with self.assertRaisesRegex(ValueError,"RECOVERY_COST_ALIAS"):b.inventory(base)
            (base/"link").unlink();os.link(base/"file",base/"hardlink")
            with self.assertRaisesRegex(ValueError,"RECOVERY_COST_TYPE"):b.inventory(base)

    def test_final_preservation_failure_cannot_claim_recovered_resources(self):
        b=ModelBackend("verify_preserved");plan,recovery,_=recovery_fixture()
        result=m.recover(plan,recovery,b,validate_settings=lambda _:None,issued_ns=1,deadline_ns=2)
        self.assertEqual("INCOMPLETE",result["status"]);self.assertNotIn("recovery",result)


class ModelBackend:
    def __init__(self,fail=None):
        self.fail=fail;self.calls=[];self.reservation=None;self.saved=None
        self.recovery_directory={"path":"/synthetic/reservation/recover001","device":11,"inode":8}
        self.original_hashes={};self.costs={}
    def do(self,name):
        self.calls.append(name)
        if self.fail==name:raise ValueError("INJECTED_FAILURE")
        return {"synthetic":name}
    def guard(self):pass
    def event(self,*args):pass
    def preflight(self):return self.do("preflight")
    def reserve(self,plan):self.reservation=True;self.do("reserve")
    def account(self):return self.do("useradd")
    def directories(self):return self.do("directories")
    def install(self):return self.do("installation")
    def roots(self):return self.do("roots")
    def parents(self):return self.do("parents")
    def snapshot(self):return [{"synthetic":True}]
    def verify_preserved(self):return self.do("verify_preserved")
    def finish(self,result):self.saved=copy.deepcopy(result)


class RecoveryOrder(unittest.TestCase):
    def test_mutation_failures_never_continue_or_retry(self):
        plan,recovery,_=recovery_fixture();order=["preflight","reserve","useradd","directories","installation","roots","parents","verify_preserved"]
        for name in order:
            b=ModelBackend(name)
            result=m.recover(plan,recovery,b,validate_settings=lambda _:None,issued_ns=1,deadline_ns=2)
            self.assertEqual(order[:order.index(name)+1],b.calls)
            self.assertEqual("BLOCKED" if name=="preflight" else "INCOMPLETE",result["status"])
            self.assertFalse(result["q2_accepted"]);self.assertEqual(result,b.saved)

    def test_separate_receipt_preserves_original_identity_and_verdict(self):
        plan,recovery,raw=recovery_fixture();before=dict(raw);b=ModelBackend()
        result=m.recover(plan,recovery,b,validate_settings=lambda _:None,issued_ns=1,deadline_ns=2)
        self.assertEqual("RESOURCES_RECOVERED",result["status"])
        self.assertEqual(recovery["plan_sha256"],result["plan_sha256"])
        self.assertEqual(recovery["original_files"]["preparation-result.json"],result["recovery"]["original_receipt_sha256"])
        self.assertEqual(m.sha(m.c.encoded(recovery)),result["recovery"]["plan_sha256"])
        self.assertEqual(before,raw);self.assertFalse(result["fixture_generated"]);self.assertFalse(result["q2_accepted"])

    def test_no_argument_entry_is_inert(self):
        process=subprocess.run([sys.executable,"-I","-B",str(PATH)],capture_output=True,timeout=10)
        self.assertEqual(3,process.returncode);self.assertEqual(b"",process.stderr)
        self.assertEqual("BLOCKED",m.c.document(process.stdout)["status"])


if __name__=="__main__":unittest.main()
