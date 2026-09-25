"""Three-phase launcher protocol models with real bounded evidence files.

Clock, manager, protected qualification and child exit are explicit models.
Actual source contracts and immutable cumulative configurations are exercised;
these tests do not claim a live systemd/quota/Q3 result.
"""
import copy
import hashlib
import io
import json
import os
import socket
import stat
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

import test_e3_quota_q2_launcher as launcher_tests
launcher, raw = launcher_tests.launcher, launcher_tests.raw
if sys.platform.startswith("linux"):
    from local_hand_jobs import budget, quota_bridge as bridge, quota_closure, runner
    from admin.local_hand_quota_observer import q2_chain as chain, q2_management, q2_coordinator, q2_capture
    from test_e3_quota_q2_chain import declaration_chain, preparation, decoded, clock, PHASES
    from test_e3_quota_q2_assembly import SESSION
    from q2_fixtures import SECOND


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux anonymous protocol/evidence files")
class ChainLauncherTests(unittest.TestCase):
    def setUp(self):
        fixture = launcher_tests.LauncherOrderingTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.root, self.repository, self.value = fixture.root, fixture.repository, fixture.value
        declaration, self.budgets = declaration_chain()
        declaration["installation"] = copy.deepcopy(self.value["assembly"]["installation"])
        for phase in PHASES:
            declaration["phases"][phase]["peer"] = copy.deepcopy(self.value["assembly"]["peer"])
        self.value.update(schema=launcher.CHAIN_SCHEMA, purpose="ISOLATED_Q2_CHAIN", assembly=declaration)
        self.value["resident"].update(schema="local-hand-q2-resident/v2", purpose="ISOLATED_Q2_CHAIN", phases=list(PHASES))
        self.value["resident"]["plan"] = dict(execution={"operation_id":"fixture"})
        self.contract = decoded(declaration)
        self.events = []; self.phase = "preflight"; self.finish = threading.Event()
        self.configs = []; self.grants = []; self.closed = {}
        self.failed_phase = self.failed_record = self.foreign_session = None
        self.false_summary = self.incomplete_capture = False
        self.current = clock("preflight")
        self.prepared = {phase:dict(event="prepared",namespace="job",identity="fixture",phase=phase,
            snapshot=preparation(declaration,self.budgets,phase),
            phase_plan={"schema":"explicitly-modeled-plan","phase":phase}) for phase in PHASES}

    def invoke(self):
        def event(name, phase=None): self.events.append((name, self.phase if phase is None else phase))
        def directory(pin, mode):
            descriptor = os.open(pin["path"],os.O_RDONLY|os.O_NOFOLLOW|os.O_DIRECTORY|os.O_CLOEXEC)
            info = os.fstat(descriptor)
            if (info.st_dev,info.st_ino,stat.S_IMODE(info.st_mode)) != (pin["device"],pin["inode"],mode):
                os.close(descriptor); raise ValueError("MODELED_DIRECTORY")
            with os.scandir(descriptor) as entries:
                if next(entries,None) is not None:
                    os.close(descriptor); raise ValueError("LAUNCHER_ALREADY_CONSUMED")
            return descriptor
        def spawn(argv, **kwargs):
            event("spawn")
            with socket.socket(fileno=os.dup(kwargs["pass_fds"][0])) as inherited:
                self.assertEqual(socket.SOCK_SEQPACKET,inherited.getsockopt(socket.SOL_SOCKET,socket.SO_TYPE))
            return SimpleNamespace(pid=os.getpid(),stdout=io.BytesIO(),stderr=io.BytesIO())
        class Channel:
            def __init__(inner,*args,**kwargs): event("channel")
            def _time(inner): return self.current["boottime_ns"]
            def receive(inner):
                event("prepared")
                packet = copy.deepcopy(self.prepared[self.phase])
                if self.foreign_session == self.phase: packet["snapshot"]["preparation"]["session"] = "b"*64
                return packet
            def send(inner, packet):
                if packet["action"] == "finish": event("finish"); self.finish.set(); return
                self.assertEqual("advance",packet["action"])
                previous = self.phase; following = PHASES[PHASES.index(previous)+1]
                self.assertEqual(dict(action="advance",value=dict(**{"from":previous,"to":following},
                    closure_digest=quota_closure.digest(dict(phase=previous,fence=self.closed[previous])))),packet)
                self.assertIn(("record_close",previous),self.events)
                event("advance"); self.phase = following; self.current = clock(following)
            def advance_phase(inner,phase): self.assertEqual(self.phase,phase); event("channel_advance")
            def close(inner): event("channel_close"); self.finish.set()
        def capture(*args,**kwargs):
            self.assertTrue(self.finish.wait(3),"modeled resident never released")
            event("capture")
            digests = {phase:quota_closure.digest(dict(phase=phase,fence=fence)) for phase,fence in self.closed.items()}
            if self.false_summary: digests["business"] = "f"*64
            summary = dict(schema="local-hand-q2-resident-result/v2",status="CHAIN_CLOSED",operation_id="fixture",
                phases=list(PHASES),closure_digests=digests,q3_accepted=False,production_supported=False)
            return dict(complete=not self.incomplete_capture,returncode=0,stdout=raw(summary),stderr=b"",error=None)
        def plan(resident,packet,grant,previous_plans):
            event("plan")
            self.assertEqual(list(PHASES[:PHASES.index(self.phase)]),list(previous_plans))
            return dict(phase=self.phase,budget_grant=copy.deepcopy(self.budgets[self.phase]),
                        quota_observation_grant=grant.as_dict())
        actual_build = chain.build_grant
        def build(*args,**kwargs):
            event("grant")
            grant = actual_build(*args,**kwargs)
            self.assertEqual(self.budgets[self.phase],grant.as_dict()["budget"])
            self.grants.append(grant); return grant
        def install(contract,grant,**kwargs):
            event("install")
            self.assertEqual(tuple(self.configs),tuple(kwargs["previousconfigs"]))
            self.assertEqual(SESSION,kwargs["session"])
            pins = dict(directory={key:self.value["assembly"]["journal"][key] for key in ("device","inode")},
                files={name:dict(device=7,inode=index+50) for index,name in enumerate(("lock","policy",
                    *(item.request.as_dict()["request_id"]+".cell" for item in self.grants)))})
            path = self.value["assembly"]["phases"][self.phase]["output"]["path"]+"/session"
            config = chain._configuration(contract,grant,"d"*64,self.configs,pins,dict(path=path,device=7,inode=70+len(self.configs)))
            self.configs.append(config)
            return dict(config=config,management_record={"phase":self.phase})
        class Record:
            def __init__(inner,pin): inner.phase=pin["phase"]; event("record",inner.phase)
            def close(inner):
                event("record_close",inner.phase)
                if self.failed_record == inner.phase: raise OSError("modeled record closure uncertainty")
        class Coordinator:
            def __init__(inner,config,*args): inner.phase=config.active().request.as_dict()["phase"]
            def run(inner):
                event("phase",inner.phase)
                if self.failed_phase==inner.phase: raise ValueError("MODELED_PHASE_UNKNOWN")
                fence={"schema":"explicitly-modeled-fence","phase":inner.phase}
                self.closed[inner.phase]=fence
                return dict(status="PHASE_CLOSED",fence=fence,q3_accepted=False,production_supported=False)
        patches=[mock.patch.object(launcher,"protected",return_value=b"modeled protected executable"),
            mock.patch.object(launcher,"controller",side_effect=lambda *_:event("controller") or dict(self.current)),
            mock.patch.object(launcher,"directory",side_effect=directory),mock.patch.object(launcher,"start_ticks",return_value=77),
            mock.patch.object(launcher.os,"readlink",return_value="mnt:[123]"),mock.patch.object(launcher.subprocess,"Popen",side_effect=spawn),
            mock.patch.object(launcher.select,"select",return_value=([True],[],[])),
            mock.patch.object(budget,"current_clock",side_effect=lambda:dict(self.current)),
            mock.patch.object(bridge,"Channel",Channel),mock.patch.object(bridge,"Client",side_effect=lambda channel:channel),
            mock.patch.object(launcher,"validate_phase_plan",side_effect=plan),mock.patch.object(chain,"build_grant",side_effect=build),
            mock.patch.object(chain,"install",side_effect=install),mock.patch.object(runner,"_quota_prepared_execution",return_value={}),
            mock.patch.object(runner,"quota_bootstrap_argv",return_value=["modeled-argv"]),
            mock.patch.object(q2_management,"controller"),mock.patch.object(q2_management,"RunRecord",Record),
            mock.patch.object(q2_coordinator,"Coordinator",Coordinator),mock.patch.object(q2_capture,"capture_existing",side_effect=capture)]
        for patch in patches: patch.start()
        try: return launcher.run(self.value,self.repository)
        finally:
            for patch in reversed(patches): patch.stop()

    def test_all_three_original_phases_finish_in_order_and_keep_cumulative_configs(self):
        result=self.invoke()
        self.assertEqual("CHAIN_CLOSED",result["status"])
        self.assertEqual(3,len(self.configs)); self.assertEqual(1,sum(event=="spawn" for event,_ in self.events))
        self.assertEqual(list(PHASES),[phase for event,phase in self.events if event=="phase"])
        for index,phase in enumerate(PHASES):
            self.assertEqual(index+1,len(self.configs[index].grants()))
            self.assertEqual("PHASE_CLOSED",json.loads((self.root/"output"/("phase-"+phase+".json")).read_bytes())["status"])
        self.assertFalse(result["q3_accepted"]); self.assertFalse(result["production_supported"])

    def test_failed_middle_phase_never_advances_or_assembles_evidence(self):
        self.failed_phase="business"; result=self.invoke()
        self.assertEqual("INCOMPLETE",result["status"])
        self.assertEqual("MODELED_PHASE_UNKNOWN",result["reason"])
        self.assertEqual(["preflight"],[phase for event,phase in self.events if event=="advance"])
        self.assertNotIn(("grant","evidence"),self.events); self.assertNotIn(("finish","evidence"),self.events)
        self.assertEqual(2,len(self.configs))

    def test_uncertain_record_close_never_authorizes_following_phase(self):
        self.failed_record="preflight"; result=self.invoke()
        self.assertEqual("INCOMPLETE",result["status"])
        self.assertFalse(any(event=="advance" for event,_ in self.events))
        self.assertEqual(1,len(self.configs))

    def test_later_foreign_broker_session_is_rejected_before_second_grant(self):
        self.foreign_session="business"; result=self.invoke()
        self.assertEqual("INCOMPLETE",result["status"])
        self.assertEqual(1,len(self.configs)); self.assertEqual(1,len(self.grants))

    def test_mismatched_final_closures_do_not_promote_complete_child_exit(self):
        self.false_summary=True; result=self.invoke()
        self.assertEqual("INCOMPLETE",result["status"])
        self.assertEqual("LAUNCHER_RESIDENT_RESULT",result["reason"])
        self.assertEqual(3,len(self.configs)); self.assertFalse(result["q3_accepted"])

    def test_missing_real_child_eof_keeps_whole_chain_incomplete(self):
        self.incomplete_capture=True; result=self.invoke()
        self.assertEqual("INCOMPLETE",result["status"])
        self.assertEqual("LAUNCHER_RESIDENT_CAPTURE",result["reason"])
        self.assertEqual(3,len(self.configs))


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux launcher phase-plan contract")
class PhasePlanTests(unittest.TestCase):
    def setUp(self):
        from q2_fixtures import make_grant
        self.resident = dict(plan=dict(execution=dict(kind="host.inspect",operation_id="fixture",python="/pinned/python",
            roots={"work":"/synthetic/work","evidence":"/synthetic/evidence","temporary":"/synthetic/temporary"}),
            registry_digest="d"*64))
        self.grants = {phase:make_grant(number=index+1,phase=phase,offset=20 if phase=="evidence" else 0,
            predecessors=[f"{number:032x}" for number in range(1,index+1)],issued=(1+index*4)*SECOND)
            for index,phase in enumerate(PHASES)}
        self.previous = {}

    def prepared(self,phase):
        from local_hand_jobs.broker import phase_plan
        from local_hand_jobs import quota_payload
        data = self.grants[phase].as_dict()
        facts = {} if phase=="preflight" else dict(inputs_stable=True,source_digest="c"*64)
        record = dict(facts=facts)
        store = None
        if phase=="evidence":
            business = self.previous["business"]
            store=data["allocation"]["retained_paths"][0]
            record["frozen_snapshot"] = dict(operation_id="fixture",reconcile_id=None,previous_seal_id=None,event_seq=7,
                root=business["bootstrap_allocation"]["roots"]["evidence"],
                broker_events=[dict(observed_at=123.125,kind="MODELED_EVENT")],
                quiescence=dict(execution_id=business["execution_id"],event_seq=7,future_starts_blocked=True,
                    tree_exited=True,collectors_stopped=True,writers_stopped=True))
        plan = phase_plan(dict(namespace="job",id="fixture",plan=self.resident["plan"],record=record),
            phase,data["budget"],allocation=data["allocation"],evidence_store_root=store)
        return dict(event="prepared",namespace="job",identity="fixture",phase=phase,
            snapshot=dict(preparation=dict(phase=phase,session=SESSION,budget=data["budget"],allocation=data["allocation"],
                generation=[1,1]),observation=None,pending=None,closed=None),
            phase_plan=quota_payload.encode_phase_plan(plan))

    def advance(self,phase):
        prepared=self.prepared(phase)
        self.previous[phase]=launcher.validate_phase_plan(self.resident,prepared,self.grants[phase],self.previous)
        return prepared

    def test_real_shared_phase_plan_keeps_original_grants_and_static_execution(self):
        for phase in PHASES:
            prepared=self.advance(phase); expected=self.previous[phase]
            self.assertEqual(self.grants[phase].as_dict(),expected["quota_observation_grant"])
            self.assertEqual(self.resident["plan"]["execution"],expected["execution"])
            self.assertEqual(prepared["snapshot"]["preparation"]["budget"],expected["budget_grant"])
        self.assertEqual(self.previous["business"]["preflight_facts"],self.previous["evidence"]["preflight_facts"])
        self.assertIs(type(self.previous["evidence"]["evidence_snapshot"]["broker_events"][0]["observed_at"]),float)
        self.assertEqual(123.125,self.previous["evidence"]["evidence_snapshot"]["broker_events"][0]["observed_at"])

    def test_base_command_budget_allocation_or_extra_plan_authority_is_rejected(self):
        from local_hand_jobs import quota_payload
        for fault in ("command","budget","allocation","extra","facts"):
            prepared=self.prepared("preflight"); plan=quota_payload.decode_phase_plan(prepared["phase_plan"])
            if fault=="command":plan["execution"]["python"]="/foreign/python"
            elif fault=="budget":plan["budget_grant"]["reserved_boottime_ns"]+=1
            elif fault=="allocation":plan["bootstrap_allocation"]["slot_id"]="foreign"
            elif fault=="extra":plan["argv"]=["/bin/sh"]
            else:plan["preflight_facts"]={"invented":True}
            prepared["phase_plan"]=quota_payload.encode_phase_plan(plan)
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                launcher.validate_phase_plan(self.resident,prepared,self.grants["preflight"],{})

    def test_phase_order_and_changed_evidence_facts_or_business_exit_binding_are_rejected(self):
        from local_hand_jobs import quota_payload
        with self.assertRaisesRegex(ValueError,"LAUNCHER_PHASE_PLAN_ORDER"):
            launcher.validate_phase_plan(self.resident,self.prepared("business"),self.grants["business"],{})
        self.advance("preflight");self.advance("business")
        for fault in ("facts","operation","root","store","execution","event","exit"):
            prepared=self.prepared("evidence");plan=quota_payload.decode_phase_plan(prepared["phase_plan"]);frozen=plan["evidence_snapshot"]
            if fault=="facts":plan["preflight_facts"]["inputs_stable"]=False
            elif fault=="operation":frozen["operation_id"]="foreign"
            elif fault=="root":frozen["root"]="/foreign/evidence"
            elif fault=="store":plan["evidence_store_root"]="/foreign/store"
            elif fault=="execution":frozen["quiescence"]["execution_id"]="foreign"
            elif fault=="event":frozen["quiescence"]["event_seq"]+=1
            else:frozen["quiescence"]["tree_exited"]=False
            prepared["phase_plan"]=quota_payload.encode_phase_plan(plan)
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                launcher.validate_phase_plan(self.resident,prepared,self.grants["evidence"],self.previous)

    def test_corrupt_encoded_plan_never_acquires_execution_authority(self):
        from local_hand_jobs.contract import JobError
        prepared=self.prepared("preflight")
        prepared["phase_plan"]["encoded_plan"]+="corrupt"
        with self.assertRaises(JobError):
            launcher.validate_phase_plan(self.resident,prepared,self.grants["preflight"],{})


if __name__ == "__main__": unittest.main()
