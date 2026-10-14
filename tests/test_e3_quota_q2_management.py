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
    def setup_manager(self, child_code="pass"):
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
            original(cap,[sys.executable,"-I","-c",child_code])
            cap.process.wait(timeout=2);cap.pump()
            self.addCleanup(cap.close_pipes)
        for patch in (mock.patch.object(m,"boottime_ns",return_value=2*SECOND),
                      mock.patch.object(m,"_boot_id",return_value=BOOT),mock.patch.object(Capture,"start",launch)):
            patch.start();self.addCleanup(patch.stop)
        return manager,events

    def stopped_manager(self):
        manager, events = self.setup_manager("raise SystemExit(7)")
        manager.begin(); manager.launch("admission")
        show = manager._show
        def running(binding, **options):
            value = show(binding, **options)
            if value["ActiveState"] == "active":value["SubState"] = "running"
            return value
        manager._show = running
        self.assertIsNone(manager.poll())  # Bind both original invocations.
        return manager, events

    def test_cancel_stops_original_units_and_drains_without_repeated_manager_polls(self):
        manager, events = self.stopped_manager()
        pin = manager.installation.active().as_dict()["query_parent"]
        with mock.patch.object(manager, "_show", wraps=manager._show) as show, \
             mock.patch.object(manager, "_command", wraps=manager._command) as command, \
             mock.patch.object(m.quota_lifecycle, "parent", side_effect=[(pin, False), (pin, False), (pin, True)]), \
             mock.patch.object(m.time, "sleep"):
            result = manager.finish_stopped()
            self.assertIs(result, manager.finish_stopped())
        self.assertEqual(4, show.call_count)
        self.assertEqual(2, command.call_count)
        self.assertEqual("STOPPED", events[-1][0])
        self.assertNotIn("CLOSED", [kind for kind, _ in events])
        self.assertEqual("local-hand-quota-management-stopped/v1", result["schema"])
        self.assertTrue(result["query_empty"] and result["management_empty"])
        for stage in result["stages"].values():
            self.assertEqual(7, stage["returncode"])  # Original nonzero exit survives.
            self.assertEqual(["stderr", "stdout"], stage["eof"])
        self.assertEqual(2, sum(kind == "DELIVERY" for kind, _ in events))

    def test_cancel_rejects_changed_identity_before_stopping_a_unit(self):
        manager, events = self.stopped_manager()
        manager.runs["listener"]["invocation"] = "f" * 32
        with mock.patch.object(manager, "_command", wraps=manager._command) as command:
            with self.assertRaisesRegex(ValueError, "INVOCATION_CHANGED"):
                manager.finish_stopped()
        command.assert_not_called()
        self.assertNotIn("STOPPED", [kind for kind, _ in events])

    def test_cancel_missing_eof_keeps_original_deadline_and_cannot_claim_stopped(self):
        manager, events = self.stopped_manager()
        pin = manager.installation.active().as_dict()["query_parent"]
        cap = manager.runs["listener"]["capture"]
        cap.eof.clear()
        clock = iter([2*SECOND, 2*SECOND, 2*SECOND, manager.end])
        with mock.patch.object(cap, "pump"), mock.patch.object(m, "boottime_ns", side_effect=lambda:next(clock)), \
             mock.patch.object(m.quota_lifecycle, "parent", return_value=(pin, True)), mock.patch.object(m.time, "sleep"):
            with self.assertRaisesRegex(ValueError, "MANAGEMENT_STOP_DEADLINE"):
                manager.finish_stopped()
        self.assertNotIn("STOPPED", [kind for kind, _ in events])

    def test_cancelled_management_record_is_durable_and_not_normal_closure(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as directory:
            path=Path(directory)/"record";path.touch(mode=0o600);info=path.stat()
            pin=dict(path=str(path),device=info.st_dev,inode=info.st_ino)
            with mock.patch.object(m.c,"open_protected",side_effect=fixture_open):
                log=m.RunRecord(pin)
                try:
                    log("INTENT", {"original": True})
                    for role in ("listener", "admission"):
                        log("DELIVERY", {"role": role});log("INVOCATION", {"role": role})
                    log("STOPPED", {"original_returncodes": [7, 7]})
                    with self.assertRaisesRegex(ValueError, "MANAGEMENT_RECORD_CLOSED"):
                        log("CLOSED", {})
                finally:log.close()
            saved=[json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual("STOPPED", saved[-1]["kind"])
            self.assertEqual([7, 7], saved[-1]["value"]["original_returncodes"])

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
