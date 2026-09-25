"""Actual broker SQLite transitions; OS and fixture stage proofs are modeled."""
import copy
import hashlib
import unittest

from local_hand_jobs import quota_contract as q, quota_closure as close
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError
import test_local_hand_jobs_quota_binding as binding_tests
from test_local_hand_jobs_quota_binding import Registry, observed
from test_e3_quota_q2_closure import complete
from q2_fixtures import SECOND


class BrokerClosureTests(unittest.TestCase):
    def setUp(self):
        self.f=binding_tests.BrokerBindingTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f
        self.grant=f.grant(f.prepare())
        f.broker.bind_observation("job",f.id,"preflight",self.grant.wire)
        f.broker._start("job",f.id,"preflight")
        execution=self.grant.request.as_dict()["execution_id"]
        f.broker._guard_start(execution,lambda:True,stage="bootstrap")
        f.now+=SECOND
        proof=dict(execution_id=execution,unit="lhj-"+hashlib.sha256((execution+":bootstrap").encode()).hexdigest()+".service",
            state="EXITED",exit_code=0,**dict.fromkeys(("future_start_blocked","tree_exited","collectors_stopped","writers_stopped","effects_checked"),True),
            result=dict(bootstrap_prepared=True,quota_observation=observed(self.grant)))
        f.broker._guard_start(execution,lambda:True,stage="helper",bootstrap_proof=proof)
        unit="lhj-"+hashlib.sha256(execution.encode()).hexdigest()+".service"
        f.f.policy.config={"process_manager":{"cgroup":"/sys/fs/cgroup/synthetic-job.slice"}}
        helper=dict(proof,unit=unit,identity=dict(cgroup="/synthetic-job.slice/"+unit,
            boot_id=self.grant.request.as_dict()["boot_id"],invocation_id="e"*32))
        f.broker._guard_start(execution,lambda:True,stage="result_reader",helper_proof=helper)
        f.now+=SECOND
        self.fence,self.proof,_,_=complete(self.grant,observation=observed(self.grant)["receipt"])

    def test_ordinary_exit_waits_for_six_stages_then_commits_phase_once(self):
        f=self.f
        f.broker._complete("job",f.id,self.proof)
        self.assertEqual("PREFLIGHT",f.row()["record"]["phase"])
        self.assertIn("preflight",f.row()["record"]["quota_pending"])
        with self.assertRaises(JobError):f.broker._start("job",f.id,"business")
        f.broker.close_observation("job",f.id,"preflight",self.fence)
        self.assertEqual("PREFLIGHT_COMPLETE",f.row()["record"]["phase"])
        f.broker.close_observation("job",f.id,"preflight",self.fence)
        self.assertEqual(1,sum(e["kind"]=="QUOTA_PHASE_CLOSED" for e in f.f.db.events("job",f.id)))
        self.assertFalse(any(k.startswith("quota_") for k in f.broker.status(f.id,f.f.owner)))
        with f.f.db.transaction() as tx:f.f.db.update(tx,"job",f.id,"FAULT",{"quota_closed":{}})
        with self.assertRaises(JobError):f.broker.close_observation("job",f.id,"preflight",self.fence)
        self.assertEqual(1,sum(e["kind"]=="QUOTA_PHASE_CLOSED" for e in f.f.db.events("job",f.id)))

    def test_no_pending_proof_missing_admission_or_changed_receipt_never_completes(self):
        f=self.f
        with self.assertRaises(JobError):f.broker.close_observation("job",f.id,"preflight",self.fence)
        f.broker._complete("job",f.id,self.proof)
        for mutation in ("admission","ordinary","receipt","identity"):
            value=copy.deepcopy(self.fence)
            if mutation=="admission":value["stages"].pop("admission")
            if mutation=="ordinary":value["ordinary_digest"]="0"*64
            if mutation=="receipt":value["receipt_digest"]="0"*64
            if mutation=="identity":value["stages"]["reader"]["identity"]["invocation_id"]="f"*32
            value["proof_digest"]=close.digest({k:v for k,v in value.items() if k!="proof_digest"})
            with self.subTest(mutation=mutation),self.assertRaises(q.QuotaError):f.broker.close_observation("job",f.id,"preflight",value)
        self.assertEqual("PREFLIGHT",f.row()["record"]["phase"])

    def test_restart_or_missing_immutable_event_cannot_reconstruct_closure(self):
        f=self.f
        f.broker._complete("job",f.id,self.proof)
        other=Broker(f.f.db,f.f.policy,Registry(),f.runner,quota_required=True)
        with self.assertRaises(q.QuotaError):other.close_observation("job",f.id,"preflight",self.fence)
        with f.f.db.transaction() as tx:f.f.db.update(tx,"job",f.id,"FAULT",{"quota_pending":{}})
        with self.assertRaises(JobError):f.broker.close_observation("job",f.id,"preflight",self.fence)
        with self.assertRaises(JobError):f.broker._complete("job",f.id,self.proof)
        self.assertEqual(1,sum(e["kind"]=="QUOTA_EXIT_PENDING" for e in f.f.db.events("job",f.id)))
        self.assertEqual(1,len(f.runner.starts))

    def test_late_or_conflicting_close_retains_original_reservation(self):
        f=self.f;f.broker._complete("job",f.id,self.proof)
        value=copy.deepcopy(self.fence);value["closed_ns"]=1000*SECOND
        value["proof_digest"]=close.digest({k:v for k,v in value.items() if k!="proof_digest"})
        with self.assertRaises(q.QuotaError):f.broker.close_observation("job",f.id,"preflight",value)
        self.assertEqual(self.grant.as_dict()["allocation"],f.row()["record"]["quota_preparations"]["preflight"]["allocation"])
        f.broker.close_observation("job",f.id,"preflight",self.fence)
        value=copy.deepcopy(self.fence);value["management_digest"]="f"*64
        value["proof_digest"]=close.digest({k:v for k,v in value.items() if k!="proof_digest"})
        with self.assertRaises(q.QuotaError):f.broker.close_observation("job",f.id,"preflight",value)


if __name__=="__main__":unittest.main()
