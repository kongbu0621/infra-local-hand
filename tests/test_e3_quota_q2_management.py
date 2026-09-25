"""Real bounded captures and record I/O; systemd/controller identities modeled."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from local_hand_jobs import quota_contract as q
from q2_fixtures import BOOT, SECOND
if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import q2_management as m
    from admin.local_hand_quota_observer.systemd_runtime import Capture, SHOW_FIELDS
    from test_e3_quota_q2_runtime import config, fixture_open


@unittest.skipUnless(sys.platform.startswith("linux"),"Linux administrator supervision")
class ManagementTests(unittest.TestCase):
    def setup_manager(self):
        cfg=config();events=[]
        env=dict(deadline_ns=10*SECOND,output_bytes=32768)
        owner=dict(boot_id=BOOT,unit="outer.service",invocation_id="e"*32,cgroup="/outer.slice/outer.service",observed_ns=SECOND)
        with mock.patch.object(m,"controller",return_value=owner):manager=m.Management(cfg,env,lambda k,v:events.append((k,v)))
        stopped=set()
        def show(binding,**options):
            role="listener" if binding.unit.startswith("lhqoc-") else "admission"
            values=dict.fromkeys((*SHOW_FIELDS,*m.runtime.UnitTransport.extra_fields),"")
            values.update(Id=binding.unit,LoadState="loaded" if role in manager.runs else "not-found",Job="")
            if role in manager.runs:
                values.update(InvocationID=("a" if role=="listener" else "b")*32,ControlGroup=binding.cgroup,
                    Slice=manager.config.query_slice,Type="exec",ExitType="cgroup",RemainAfterExit="yes",Restart="no",KillMode="control-group",
                    ActiveState="inactive" if binding.unit in stopped else "active",SubState="dead" if binding.unit in stopped else "exited",
                    ExecMainCode="1",ExecMainStatus="0",Result="success")
            return values
        def command(arguments,**options):
            self.assertEqual("stop",arguments[0]);stopped.add(arguments[1]);return b""
        manager._show=show;manager._command=command;manager._parent_empty=lambda binding:True
        original=Capture.start
        def launch(cap,argv):
            original(cap,[sys.executable,"-I","-c","pass"])
            cap.process.wait(timeout=2);cap.pump()
            self.addCleanup(cap.close_pipes)
        for patch in (mock.patch.object(m,"boottime_ns",return_value=2*SECOND),
                      mock.patch.object(m,"_boot_id",return_value=BOOT),mock.patch.object(Capture,"start",launch)):
            patch.start();self.addCleanup(patch.stop)
        return manager,events

    def test_joint_management_capture_binds_both_units_and_never_relaunches(self):
        manager,events=self.setup_manager()
        manager.begin();manager.launch("admission")
        self.assertIsNone(manager.poll())
        result=manager.poll();self.assertEqual({"collector","admission"},set(result["stages"]))
        manager.finish()
        self.assertEqual(["INTENT","DELIVERY","DELIVERY","INVOCATION","INVOCATION","CLOSED"],[k for k,_ in events])
        with self.assertRaises(q.QuotaError):manager.begin()
        with self.assertRaises(q.QuotaError):manager.launch("admission")

    def test_missing_admission_capture_or_changed_invocation_cannot_close(self):
        manager,_=self.setup_manager();manager.begin();manager.launch("admission");manager.poll()
        cap=manager.runs["admission"]["capture"]
        cap.error="CAPTURE_BYTE_LIMIT"
        self.assertIsNone(manager.poll())
        with self.assertRaises(q.QuotaError):manager.finish()
        manager.runs["admission"]["invocation"]="f"*32
        with self.assertRaises(ValueError):manager.poll()
        self.assertIsNotNone(manager.failure)
        with self.assertRaises(q.QuotaError):manager.finish()

    def test_pending_delivery_waits_without_relaunch_or_inventing_exit(self):
        manager,events=self.setup_manager();manager.begin();manager.launch("admission")
        show=manager._show
        def absent(binding,**options):
            value=show(binding,**options);value["LoadState"]="not-found";return value
        with mock.patch.object(manager,"_show",side_effect=absent), \
             mock.patch.object(manager.runs["listener"]["capture"].process,"poll",return_value=None), \
             mock.patch.object(manager.runs["admission"]["capture"].process,"poll",return_value=None):
            self.assertIsNone(manager.poll())
            self.assertFalse(any(part["stop_attempted"] for part in manager.runs.values()))
            self.assertEqual(2,sum(k=="DELIVERY" for k,_ in events))
        self.assertIsNone(manager.poll());self.assertIsNotNone(manager.poll())
        with mock.patch.object(m,"_boot_id",return_value="changed"),self.assertRaises(q.QuotaError):manager.finish()

    def test_fsync_failure_leaves_consumed_record_and_never_reopens_empty(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as directory:
            path=Path(directory)/"record";path.touch(mode=0o600);s=path.stat()
            pin=dict(path=str(path),device=s.st_dev,inode=s.st_ino)
            with mock.patch.object(m.c,"open_protected",side_effect=fixture_open):
                log=m.RunRecord(pin)
                try:
                    with mock.patch.object(os,"fsync",side_effect=OSError("fault")),self.assertRaises(OSError):log("INTENT",{"fixed":True})
                    with self.assertRaises(q.QuotaError):log("DELIVERY",{})
                finally:log.close()
                self.assertTrue(path.read_bytes())
                with self.assertRaises(q.QuotaError):m.RunRecord(pin)

    def test_pipe_close_failure_cannot_commit_closed_record(self):
        manager,events=self.setup_manager();manager.begin();manager.launch("admission");manager.poll();manager.poll()
        cap=manager.runs["admission"]["capture"]
        with mock.patch.object(cap,"close_pipes",side_effect=lambda:setattr(cap,"error","CAPTURE_CLOSE_UNCERTAIN")),self.assertRaises(q.QuotaError):
            manager.finish()
        self.assertFalse(any(k=="CLOSED" for k,_ in events))
        with self.assertRaises(q.QuotaError):manager.finish()

    def test_two_controllers_cannot_acquire_same_existing_record(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as directory:
            path=Path(directory)/"record";path.touch(mode=0o600);s=path.stat()
            pin=dict(path=str(path),device=s.st_dev,inode=s.st_ino)
            with mock.patch.object(m.c,"open_protected",side_effect=fixture_open):
                first=m.RunRecord(pin)
                try:
                    with self.assertRaises(BlockingIOError):m.RunRecord(pin)
                    first("INTENT",{"original":True})
                    with self.assertRaises(q.QuotaError):first("CLOSED",{})
                    with self.assertRaises(q.QuotaError):first("DELIVERY",{"role":"listener"})
                finally:first.close()


class BatchEntryTests(unittest.TestCase):
    def test_default_entry_reports_blocked_without_mutating_host(self):
        entry=Path(__file__).parent/"e3_host/q2_batch_check.py"
        result=subprocess.run([sys.executable,"-I","-B",str(entry)],capture_output=True,timeout=5)
        self.assertEqual(3,result.returncode)
        value=json.loads(result.stdout)
        self.assertEqual("BLOCKED",value["status"])
        self.assertEqual("NOT_RUN",value["q3_status"])
        self.assertFalse(value["production_supported"])

    def test_fixture_paths_extra_keys_and_digests_are_strict(self):
        spec=importlib.util.spec_from_file_location("fixture_check",Path(__file__).parent/"e3_host/q2_batch_check.py")
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        value=dict(schema=module.SCHEMA,purpose="ISOLATED_Q2_CHECK",source_commit="a"*40,files={"tests/e3_host/q2_batch_check.py":"b"*64},
            observer={},ordinary={},controller_envelope={},management_record={})
        raw=json.dumps(value).encode();self.assertEqual(value,module.decode(raw,hashlib.sha256(raw).hexdigest()))
        for mutation in ("extra","path","hash","schema"):
            item=copy.deepcopy(value)
            if mutation=="extra":item["supported"]=True
            if mutation=="path":item["files"]={"../run.py":"b"*64}
            if mutation=="hash":item["files"]["tests/e3_host/q2_batch_check.py"]=False
            if mutation=="schema":item["schema"]="local-hand-q2-fixture/v0"
            raw=json.dumps(item).encode()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):module.decode(raw,hashlib.sha256(raw).hexdigest())


if __name__=="__main__":unittest.main()
