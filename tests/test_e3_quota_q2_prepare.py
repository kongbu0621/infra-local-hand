"""Model mutation failure boundaries and real create-only files/pipe capture.

No test creates accounts, quota domains or systemd objects. Synthetic completion
is explicitly RESOURCES_PREPARED, never a claim of guest/Q2 acceptance.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from test_e3_quota_q2_prepare_contract import fixture

PATH=Path(__file__).parent/"e3_host/q2_prepare.py"
spec=importlib.util.spec_from_file_location("_prepare_test",PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class ModelBackend:
    def __init__(self,fail=None):self.fail=fail;self.calls=[];self.reservation=None;self.saved=None
    def do(self,name):
        self.calls.append(name)
        if name==self.fail:raise ValueError("INJECTED_FAILURE")
        return {"test_only":name}
    def guard(self):pass
    def event(self,*args):pass
    def preflight(self):self.do("preflight");return {"retained_before":self.snapshot()}
    def reserve(self,plan):self.reservation=True;self.do("reserve")
    def account(self):return self.do("account")
    def directories(self):return self.do("directories")
    def install(self):return self.do("install")
    def roots(self):return self.do("roots")
    def parents(self):return self.do("parents")
    def snapshot(self):return [{"test_only":"retained"}]
    def finish(self,value):self.saved=copy.deepcopy(value)


class ProvisionOrder(unittest.TestCase):
    def test_preflight_and_settings_failure_have_no_mutation(self):
        b=ModelBackend("preflight");result=m.prepare(fixture(),b,validate_settings=lambda _:None)
        self.assertEqual("BLOCKED",result["status"]);self.assertEqual(["preflight"],b.calls)
        b=ModelBackend()
        with self.assertRaisesRegex(ValueError,"SETTINGS"):
            m.prepare(fixture(),b,validate_settings=lambda _:(_ for _ in ()).throw(ValueError("SETTINGS")))
        self.assertEqual([],b.calls)

    def test_all_mutation_boundaries_retain_and_never_continue(self):
        order=["preflight","reserve","account","directories","install","roots","parents"]
        for step in order[1:]:
            b=ModelBackend(step);result=m.prepare(fixture(),b,validate_settings=lambda _:None)
            with self.subTest(step=step):
                self.assertEqual("INCOMPLETE",result["status"])
                self.assertEqual(order[:order.index(step)+1],b.calls)
                self.assertEqual(result,b.saved);self.assertFalse(result["q2_accepted"])

    def test_resource_preparation_does_not_claim_fixture_or_acceptance(self):
        b=ModelBackend();result=m.prepare(fixture(),b,validate_settings=lambda _:None)
        self.assertEqual("RESOURCES_PREPARED",result["status"])
        self.assertFalse(result["fixture_generated"]);self.assertFalse(result["q3_accepted"])
        self.assertFalse(result["production_supported"])

    def test_retained_change_prevents_prepared_result(self):
        b=ModelBackend();b.snapshot=mock.Mock(side_effect=[[1],[2]])
        result=m.prepare(fixture(),b,validate_settings=lambda _:None)
        self.assertEqual("INCOMPLETE",result["status"]);self.assertEqual("PREPARE_RETAINED_CHANGED",result["reason"])

    def test_no_argument_entry_blocks_before_host_operations(self):
        p=subprocess.run([sys.executable,"-I","-B",str(PATH)],capture_output=True,timeout=10)
        self.assertEqual(3,p.returncode);self.assertEqual(b"",p.stderr)
        self.assertEqual("BLOCKED",json.loads(p.stdout)["status"])


@unittest.skipUnless(sys.platform.startswith("linux"),"Linux no-follow and process-group primitives")
class RealFileAndCapture(unittest.TestCase):
    def test_later_project_collision_is_rejected_before_any_quota_mutation(self):
        b=m.LinuxBackend(fixture());b.command=mock.Mock()
        with mock.patch.object(m,"Quota") as quota,mock.patch.object(m,"create_directory") as create:
            quota.return_value.unused.side_effect=ValueError("PREPARE_PROJECT_BECAME_OCCUPIED")
            with self.assertRaisesRegex(ValueError,"PREPARE_PROJECT_BECAME_OCCUPIED"):b.roots()
        create.assert_not_called();b.command.assert_not_called()

    def test_shared_project_after_assignment_does_not_set_limits(self):
        b=m.LinuxBackend(fixture());b.command=mock.Mock()
        with mock.patch.object(m,"Quota") as quota,mock.patch.object(m,"create_directory"):
            quota.return_value.block.return_value={"inodes":2}
            with self.assertRaisesRegex(ValueError,"PREPARE_PROJECT_ASSIGNMENT_UNCERTAIN"):b.roots()
        self.assertEqual(1,b.command.call_count)
        self.assertEqual(b.tool("chattr"),b.command.call_args.args[0][0])

    def test_reservation_existing_and_symlink_fail_without_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"record";path.write_bytes(b"original")
            with mock.patch.object(m,"opened",side_effect=lambda p,**_:os.open(p,os.O_RDONLY|os.O_DIRECTORY)):
                with self.assertRaises(FileExistsError):m.create_file(path,b"replacement",owner=os.getuid(),gid=os.getgid())
            self.assertEqual(b"original",path.read_bytes())
            link=Path(td)/"link";link.symlink_to(path)
            with mock.patch.object(m,"opened",side_effect=lambda p,**_:os.open(p,os.O_RDONLY|os.O_DIRECTORY)):
                with self.assertRaises(FileExistsError):m.create_file(link,b"replacement",owner=os.getuid(),gid=os.getgid())
            self.assertEqual(b"original",path.read_bytes())

    def backend(self):
        b=m.LinuxBackend(fixture());b.event=mock.Mock();return b

    def test_capture_requires_actual_exit_and_both_eofs(self):
        b=self.backend();raw=b.command([sys.executable,"-I","-B","-c","import sys;print('hello');sys.stderr.write('err')"])
        self.assertEqual(b"hello\n",raw)
        record=b.event.call_args.args[1]
        self.assertEqual(0,record["returncode"]);self.assertEqual(["stderr","stdout"],record["eof"])

    def test_output_limit_is_retained_not_silently_truncated_success(self):
        b=self.backend();b.plan["budgets"]["command_output_bytes"]=1024
        with self.assertRaisesRegex(ValueError,"PREPARE_COMMAND_OUTPUT_LIMIT"):
            b.command([sys.executable,"-I","-B","-c","import os;os.write(1,b'x'*8192)"])
        result=b.event.call_args.args[1]
        self.assertEqual(1024,len(bytes.fromhex(result["stdout"])))
        self.assertEqual("PREPARE_COMMAND_OUTPUT_LIMIT",result["failure"])

    def test_descendant_holding_pipes_does_not_report_complete(self):
        b=self.backend();b.plan["budgets"]["command_seconds"]=1
        with self.assertRaisesRegex(ValueError,"PREPARE_COMMAND_TIMEOUT"):
            b.command([sys.executable,"-I","-B","-c",
                       "import os,time; pid=os.fork(); time.sleep(20) if pid==0 else None"])
        record=b.event.call_args.args[1]
        self.assertNotEqual(["stderr","stdout"],record["eof"])

    def test_global_deadline_still_records_captured_result(self):
        b=m.LinuxBackend(fixture());b.reservation=Path("/synthetic/reserved");b.max_events=1024
        b.log_inode_limit=2048;b.log_byte_limit=32*1024**2
        b.deadline=time.monotonic_ns()+200_000_000
        saved=[]
        with mock.patch.object(m,"create_file",side_effect=lambda p,raw,**_:saved.append((str(p),json.loads(raw)))):
            with self.assertRaisesRegex(ValueError,"PREPARE_COMMAND_TIMEOUT"):
                b.command([sys.executable,"-I","-B","-c","import os,time;os.write(1,b'before-timeout');time.sleep(20)"])
        result=saved[-1][1]
        self.assertTrue(saved[-1][0].endswith("command-result.json"))
        self.assertEqual(b"before-timeout",bytes.fromhex(result["stdout"]))
        self.assertEqual("PREPARE_COMMAND_TIMEOUT",result["failure"])

    def test_record_capacity_is_checked_before_process_creation(self):
        b=m.LinuxBackend(fixture());b.reservation=Path("/synthetic/reserved");b.max_events=0
        with mock.patch.object(m.subprocess,"Popen") as spawn:
            with self.assertRaisesRegex(ValueError,"PREPARE_COMMAND_RECORD_BUDGET"):
                b.command([sys.executable,"-V"])
        spawn.assert_not_called()


if __name__=="__main__":unittest.main()
