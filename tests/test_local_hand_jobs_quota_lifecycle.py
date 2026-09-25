"""Actual anonymous pipes/child exits; manager and cgroup facts are modeled."""
import copy
import contextlib
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from local_hand_jobs import budget, quota_contract as q
from q2_fixtures import BOOT, SECOND
if sys.platform.startswith("linux"):
    from local_hand_jobs import quota_lifecycle as life, runner


@unittest.skipUnless(sys.platform.startswith("linux"),"Linux pipe supervision")
class LifecycleTests(unittest.TestCase):
    def setup_part(self, code="pass"):
        proc=subprocess.Popen([sys.executable,"-I","-c",code],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for pipe in (proc.stdout,proc.stderr):os.set_blocking(pipe.fileno(),False)
        proc.wait(timeout=2)
        def cleanup():
            for pipe in (proc.stdout,proc.stderr):pipe.close()
        self.addCleanup(cleanup)
        pin=dict(path="/fixed.slice",device=4,inode=81)
        part=dict(boot_id=BOOT,unit="fixed.service",stage="helper",invocation_id=None,
            launch=proc,pipe_nonblocking=True,quota_transport=life.Transport(65536),quota_parent=pin,
            cgroup_parent="/sys/fs/cgroup/fixed.slice",phase_deadline_boottime_ns=30*SECOND,execution_id="fixed")
        props=dict(Id="fixed.service",LoadState="loaded",ActiveState="active",SubState="exited",
            ControlGroup="/fixed.slice/fixed.service",InvocationID="a"*32,Job="",ExecMainCode="1",
            ExecMainStatus="0",Result="success",Restart="no",TriggeredBy="",ExecStop="",ExecStopPost="",
            ExecReload="",KillMode="control-group",Type="exec",ExitType="cgroup",RemainAfterExit="yes",
            ExecStartPre="",ExecStartPost="",OnFailure="",OnSuccess="",RestartForceExitStatus="")
        calls=[]
        def command(*args):
            calls.append(args)
            if args[0]=="stop":props.update(ActiveState="inactive",SubState="dead",ControlGroup="");raw=b""
            elif "--value" in args:raw=(props["InvocationID"]+"\n").encode()
            else:raw="".join(k+"="+v+"\n" for k,v in props.items()).encode()
            return subprocess.CompletedProcess(args,0,raw,b"")
        manager=mock.Mock(_command=command)
        self.clock=mock.patch.object(budget,"current_clock",return_value={"boot_id":BOOT,"boottime_ns":2*SECOND})
        self.parent=mock.patch.object(life,"parent",return_value=(pin,True))
        self.clock.start();self.parent.start();self.addCleanup(self.clock.stop);self.addCleanup(self.parent.stop)
        return part,props,manager,calls

    def test_original_child_two_eofs_and_ordered_stop_create_a_closed_stage(self):
        part,props,manager,calls=self.setup_part()
        self.assertEqual("UNKNOWN",life.observe(manager,part,runner._unknown)["state"])
        result=life.observe(manager,part,runner._unknown)
        self.assertEqual("EXITED",result["state"])
        self.assertTrue(all(part["quota_exit"][key] for key in q.EXIT_FLAGS))
        self.assertEqual(1,sum(args[0]=="stop" for args in calls))
        self.assertEqual(result,life.observe(manager,part,runner._unknown))

    def unload(self, props):
        props.update(LoadState="not-found", ActiveState="inactive", SubState="dead",
                     ControlGroup="", InvocationID="", Job="", ExecMainCode="0", ExecMainStatus="0")

    def test_post_stop_transient_collection_preserves_original_terminal_and_exit(self):
        part,props,manager,calls=self.setup_part()
        life.observe(manager,part,runner._unknown)
        terminal=copy.deepcopy(part["quota_terminal"])
        self.unload(props)
        result=life.observe(manager,part,runner._unknown)
        self.assertEqual("EXITED",result["state"])
        self.assertEqual("a"*32,result["identity"]["invocation_id"])
        self.assertEqual(terminal,part["quota_terminal"])
        self.assertEqual({"stdout","stderr"},part["quota_transport"].eof)
        self.assertTrue(all(part["quota_exit"][key] for key in q.EXIT_FLAGS))
        self.assertEqual(1,sum(args[0]=="stop" for args in calls))

    def test_missing_before_retained_stop_never_adopts_a_unit(self):
        part,props,manager,calls=self.setup_part()
        self.unload(props)
        with self.assertRaisesRegex(q.QuotaError,"ORIGINAL_UNIT_MISSING"):
            life.observe(manager,part,runner._unknown)
        self.assertNotIn("quota_exit",part)
        self.assertEqual(0,sum(args[0]=="stop" for args in calls))

    def test_post_stop_absence_still_requires_all_original_exit_evidence(self):
        faults=("terminal_missing","stop_ack","stop_attempt","launch_ack","identity_missing",
                "terminal_identity","terminal_unit","terminal_running","terminal_config","unit",
                "invocation","cgroup","queue","active","deadline","parent","occupied","client","eof")
        for fault in faults:
            with self.subTest(fault=fault),contextlib.ExitStack() as patches:
                part,props,manager,calls=self.setup_part()
                life.observe(manager,part,runner._unknown)
                self.unload(props)
                if fault=="terminal_missing":part.pop("quota_terminal")
                if fault=="stop_ack":part["quota_stop_ok"]=False
                if fault=="stop_attempt":part["quota_stop_attempted"]=False
                if fault=="launch_ack":part["launch_acked"]=False
                if fault=="identity_missing":part["invocation_id"]=None
                if fault=="terminal_identity":part["quota_terminal"]["InvocationID"]="b"*32
                if fault=="terminal_unit":part["quota_terminal"]["Id"]="another.service"
                if fault=="terminal_running":part["quota_terminal"].update(ActiveState="active",SubState="running")
                if fault=="terminal_config":part["quota_terminal"]["OnSuccess"]="another.service"
                if fault=="unit":props["Id"]="another.service"
                if fault=="invocation":props["InvocationID"]="b"*32
                if fault=="cgroup":props["ControlGroup"]="/fixed.slice/another.service"
                if fault=="queue":props["Job"]="1 /queued/start"
                if fault=="active":props["ActiveState"]="active"
                if fault=="deadline":part["phase_deadline_boottime_ns"]=SECOND
                if fault=="parent":patches.enter_context(mock.patch.object(life,"parent",side_effect=q.QuotaError("ORDINARY_PARENT_CHANGED")))
                if fault=="occupied":patches.enter_context(mock.patch.object(life,"parent",return_value=(part["quota_parent"],False)))
                if fault=="client":part["launch"].returncode=-9
                if fault=="eof":
                    part["quota_transport"].eof={"stdout"}
                    patches.enter_context(mock.patch.object(part["quota_transport"],"pump"))
                with self.assertRaises(q.QuotaError):life.observe(manager,part,runner._unknown)
                self.assertNotIn("quota_exit",part)
                self.assertEqual(1,sum(args[0]=="stop" for args in calls))

    def test_same_real_exit_without_original_eof_does_not_prove_closed(self):
        part,props,manager,_=self.setup_part()
        original=part["launch"].stdout;original.close()
        read,write=os.pipe();os.set_blocking(read,False)
        part["launch"].stdout=os.fdopen(read,"rb",buffering=0)
        self.addCleanup(os.close,write)
        self.addCleanup(part["launch"].stdout.close)
        life.observe(manager,part,runner._unknown)
        with self.assertRaisesRegex(q.QuotaError,"CLIENT_EOF"):life.observe(manager,part,runner._unknown)
        self.assertNotIn("quota_exit",part)

    def test_killed_original_client_is_not_replaced_by_unit_success(self):
        part,props,manager,_=self.setup_part()
        part["launch"].returncode=-9
        life.observe(manager,part,runner._unknown)
        with self.assertRaisesRegex(q.QuotaError,"CLIENT_EOF"):life.observe(manager,part,runner._unknown)

    def test_new_invocation_queued_activation_and_reboot_keep_original_unknown(self):
        for fault in ("invocation","restart","activation","queue","boot","deadline","parent","recovery","OnSuccess","ExecStartPost","close"):
            with self.subTest(fault=fault):
                part,props,manager,calls=self.setup_part()
                life.observe(manager,part,runner._unknown)
                if fault=="invocation":props["InvocationID"]="b"*32
                if fault=="restart":props["Restart"]="always"
                if fault=="activation":props["TriggeredBy"]="fixed.socket"
                if fault=="queue":props["Job"]="1 /queued/start"
                if fault=="boot":part["boot_id"]="0"*36
                if fault=="deadline":part["phase_deadline_boottime_ns"]=SECOND
                if fault=="recovery":part["recovered"]=True
                if fault in ("OnSuccess","ExecStartPost"):props[fault]="another.service"
                patch=mock.patch.object(life,"parent",side_effect=q.QuotaError("ORDINARY_PARENT_CHANGED")) if fault=="parent" else mock.patch.object(life,"parent",return_value=(part["quota_parent"],True))
                if fault=="close":patch=mock.patch.object(part["launch"].stderr,"close",side_effect=OSError("fault"))
                with patch,self.assertRaises(q.QuotaError):life.observe(manager,part,runner._unknown)
                self.assertNotIn("quota_exit",part)
                self.assertEqual(1,sum(args[0]=="stop" for args in calls))

    def test_transport_overflow_is_sticky_and_bounded_per_tick(self):
        part,_,_,_=self.setup_part("import sys;sys.stdout.write('x'*1024)")
        cap=part["quota_transport"]=life.Transport(10)
        cap.pump(part);cap.pump(part)
        self.assertEqual("PIPE_BYTE_LIMIT",cap.error)
        self.assertEqual({"stdout","stderr"},cap.eof)
        self.assertEqual(1024,cap.total)


if __name__=="__main__":unittest.main()
