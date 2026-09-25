"""Durable six-stage closure tests; service/cgroup identities are synthetic."""
import copy
import hashlib
import sys
import unittest

from local_hand_jobs import quota_closure as close, quota_contract as q
from q2_fixtures import make_grant, peer, receipt, SECOND, encoded


def complete(grant, *, at=None, observation=None):
    at = grant.as_dict()["management"]["issued_ns"] + 2*SECOND if at is None else at
    raw = receipt(grant, start=at-SECOND, finish=at-SECOND+10) if observation is None else observation
    got = q.decode_receipt(encoded(raw), grant.request, grant.as_dict()["roots"], now_ns=at)
    client = peer(grant)
    stages = {}
    for name in close.STAGES:
        inv = client["invocation_id"] if name == "bootstrap" else raw["query"]["invocation_id"] if name == "query" else "e"*32
        stages[name] = dict(**dict.fromkeys(q.EXIT_FLAGS, True), identity=close.stage_identity(grant, name, client, inv),
            observed_ns=at, proof_digest=raw["exit"]["proof_digest"] if name == "query" else "d"*64)
    ordinary = dict(state="EXITED", future_start_blocked=True, tree_exited=True, collectors_stopped=True,
        writers_stopped=True, effects_checked=True, exit_code=0, facts={"inputs_stable":True}, result={},
        quota_stage_exits={name:stages[name] for name in close.ORDINARY})
    parents = {name:dict(identity=pin, populated=0, observed_ns=at, proof_digest="a"*64)
        for name,pin in (("ordinary",client["parent"]),("query",grant.as_dict()["query_parent"]),
                         ("management",grant.as_dict()["management_parent"]))}
    value = dict(schema=close.SCHEMA, request_digest=grant.request.digest, receipt_digest=hashlib.sha256(got.wire).hexdigest(),
        boot_id=grant.request.as_dict()["boot_id"], execution_id=grant.request.as_dict()["execution_id"], closed_ns=at,
        ordinary_digest=close.digest(ordinary), management_digest="b"*64, stages=stages, parents=parents)
    value["proof_digest"] = close.digest(value)
    return value, ordinary, got, client


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.grant = make_grant()
        self.value,self.ordinary,self.receipt,self.peer = complete(self.grant)

    def check(self, value=None, **options):
        return close.decode(self.value if value is None else value,self.grant,self.receipt,self.peer,
            now_ns=3*SECOND,ordinary_digest=close.digest(self.ordinary),**options)

    def test_six_stages_and_three_parents_bind_the_whole_phase(self):
        self.assertEqual(self.value,self.check())
        self.assertEqual(set(close.STAGES),set(self.value["stages"]))

    def test_missing_stage_eof_exit_parent_or_invocation_is_not_closed(self):
        for stage in close.STAGES:
            for flag in q.EXIT_FLAGS:
                value=copy.deepcopy(self.value);value["stages"][stage][flag]=False
                value["proof_digest"]=close.digest({k:v for k,v in value.items() if k!="proof_digest"})
                with self.subTest(stage=stage,flag=flag),self.assertRaises(q.QuotaError):self.check(value)
        for name in self.value["parents"]:
            value=copy.deepcopy(self.value);value["parents"][name]["populated"]=1
            value["proof_digest"]=close.digest({k:v for k,v in value.items() if k!="proof_digest"})
            with self.subTest(parent=name),self.assertRaises(q.QuotaError):self.check(value)

    def test_wrong_original_boot_or_replaced_parent_remains_unresolved(self):
        for change in ("boot","parent","query","bootstrap","missing-admission","legacy","late-management","late-parent"):
            value=copy.deepcopy(self.value)
            if change=="boot":value["boot_id"]="00000000-0000-0000-0000-000000000000"
            if change=="parent":value["parents"]["ordinary"]["identity"]["inode"]+=1
            if change=="query":value["stages"]["query"]["identity"]["invocation_id"]="f"*32
            if change=="bootstrap":value["stages"]["bootstrap"]["identity"]["invocation_id"]="f"*32
            if change=="missing-admission":value["stages"].pop("admission")
            if change=="legacy":value["schema"]="local-hand-quota-phase-closed/v1"
            if change=="late-management":value["stages"]["admission"]["observed_ns"]=11*SECOND
            if change=="late-parent":value["parents"]["ordinary"]["observed_ns"]-=1
            value["proof_digest"]=close.digest({k:v for k,v in value.items() if k!="proof_digest"})
            with self.subTest(change=change),self.assertRaises(q.QuotaError):self.check(value)

    def test_ordinary_digest_and_independent_original_identities_cannot_be_substituted(self):
        changed=copy.deepcopy(self.value);changed["ordinary_digest"]="0"*64
        changed["proof_digest"]=close.digest({k:v for k,v in changed.items() if k!="proof_digest"})
        with self.assertRaises(q.QuotaError):self.check(changed)
        originals={n:p["identity"] for n,p in self.value["stages"].items()}
        originals=copy.deepcopy(originals);originals["admission"]["invocation_id"]="f"*32
        with self.assertRaises(q.QuotaError):self.check(originals=originals)


@unittest.skipUnless(sys.platform.startswith("linux"),"Linux administrative journal")
class JournalClosureTests(unittest.TestCase):
    def test_real_journal_v2_closure_and_reopen_preserve_six_stage_record(self):
        from test_e3_quota_q2_service import ServiceTests
        from admin.local_hand_quota_observer.q2_service import Service
        f=ServiceTests();f.setUp();self.addCleanup(f.doCleanups)
        # Use the real journal/dispatch test fixture, no host invocation implied.
        journal=f.open().journal
        service=Service(journal,clock=lambda:dict(f.clock),closure_version=2)
        result=service.handle(f.first.request.wire,peer=peer(f.first),expected_peer=peer(f.first),dispatch=f.dispatch)
        value,_,got,client=complete(f.first,observation=q._load(result.receipt,q.RESPONSE_LIMIT,8))
        from q2_fixtures import fence
        with self.assertRaises(q.QuotaError):service.close_phase(f.first.request,fence(f.first,result.receipt))
        f.clock["ns"]=3*SECOND
        service.close_phase(f.first.request,value)
        service.close_phase(f.first.request,value)
        with journal.locked():self.assertEqual(value,journal.scan()[f.first.request.as_dict()["request_id"]]["closed"])
        reopened=f.open().journal
        with reopened.locked():self.assertEqual(value,reopened.scan()[f.first.request.as_dict()["request_id"]]["closed"])


if __name__ == "__main__":unittest.main()
