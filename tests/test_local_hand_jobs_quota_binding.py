"""Durable SQLite and anonymous-pipe checks; OS supervision remains modeled."""
import copy
import hashlib
import os
import sys
import unittest
from unittest import mock

from local_hand_jobs import budget, quota_binding as b, quota_contract as q, quota_grant as g
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError
from q2_fixtures import make_grant, grant_data, encoded, receipt, SECOND
import test_local_hand_jobs_broker as fixtures


def observed(grant):
    facts = receipt(grant, start=grant.as_dict()["management"]["issued_ns"] + SECOND,
                    finish=grant.as_dict()["management"]["issued_ns"] + SECOND)
    raw = encoded(facts)
    decoded = q.decode_receipt(raw, grant.request, grant.as_dict()["roots"], now_ns=facts["finished_ns"])
    return {"schema": "local-hand-bootstrap-quota/v1", "grant_digest": grant.digest,
            "request_digest": grant.request.digest, "receipt_digest": hashlib.sha256(decoded.wire).hexdigest(),
            "domain_hard_bytes": decoded.domain_hard_bytes, "receipt": facts}


class ReceiptPipeTests(unittest.TestCase):
    def test_real_fragmented_anonymous_pipe_and_eof(self):
        grant = make_grant(); packet = b.frame(observed(grant)); reader = b.Pipe()
        r, w = os.pipe()
        try:
            os.write(w, packet[:19]); reader.feed(os.read(r, 19))
            with self.assertRaises(q.QuotaError): reader.finish(grant, now_ns=2*SECOND)
            os.write(w, packet[19:]); os.close(w); w = -1
            while not reader.eof:
                reader.feed(os.read(r, 29))
            self.assertEqual(grant.digest, reader.finish(grant, now_ns=2*SECOND)["grant_digest"])
        finally:
            os.close(r)
            if w >= 0: os.close(w)

    def test_partial_trailing_oversize_and_expired_are_unresolved(self):
        grant = make_grant(); packet = b.frame(observed(grant))
        for raw, now in ((packet[:-1],2*SECOND), (packet+b"x",2*SECOND),
                         (b"x"*(q.RESPONSE_LIMIT+5),2*SECOND), (packet,11*SECOND)):
            with self.subTest(size=len(raw)):
                p = b.Pipe(); p.feed(raw); p.feed(b"")
                with self.assertRaises(q.QuotaError): p.finish(grant, now_ns=now)

    def test_false_exit_changed_parent_and_foreign_grant_rejected(self):
        grant = make_grant()
        for field in ("exit", "parent", "digest", "domain"):
            value = observed(grant)
            if field == "exit": value["receipt"]["exit"]["stdout_eof"] = False
            if field == "parent": value["receipt"]["query"]["cgroup"] = "/foreign/"+grant.request.query_unit
            if field == "digest": value["grant_digest"] = "0"*64
            if field == "domain": value["domain_hard_bytes"] = True
            value["receipt_digest"] = hashlib.sha256(encoded(value["receipt"])).hexdigest()
            with self.subTest(field=field), self.assertRaises(q.QuotaError):
                b.validate_observation(value, grant, now_ns=2*SECOND)


class Registry(fixtures.RegistryFixture):
    def resolve(self, *args, **kwargs):
        plan = super().resolve(*args, **kwargs)
        plan["budgets"].update(wall_seconds=90, cpu_seconds=30, temporary_bytes=1024**2, reservation_bytes=4*1024**2)
        plan["reservation_bytes"] = 4*1024**2
        plan["execution"] = {"roots": {role:"/synthetic/original/"+role for role in ("work","evidence","temporary")}}
        return plan


class BrokerBindingTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.BrokerTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.now = 100*SECOND
        self.patch = mock.patch.object(budget, "current_clock", side_effect=lambda: {
            "boot_id": "11111111-2222-3333-4444-555555555555", "boottime_ns": self.now})
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.runner = fixtures.DeferredDeliverySupervisor()
        self.f.policy.limits = dict(self.f.policy.limits, retained_bytes=1024**3)
        profile = copy.deepcopy(self.f.policy.profiles["fixture"] if "fixture" in self.f.policy.profiles else next(iter(self.f.policy.profiles.values())))
        slots = [{"slot_id":"quota-slot", "roots": {role:{"path":"/synthetic/"+role,"device":7,"inode":i+101,"uid":1234}
                 for i, role in enumerate(("work","evidence","temporary"))}}]
        profile["bootstrap_slots"] = slots
        key = self.f.request["profile_ref"]
        self.f.policy.profiles = dict(self.f.policy.profiles, **{key:profile})
        self.broker = Broker(self.f.db, self.f.policy, Registry(), self.runner, quota_required=True)
        self.broker.submit(self.f.request, self.f.owner)
        self.id = self.f.request["operation_id"]

    def row(self): return self.f.db.get("job", self.id)
    def prepare(self):
        self.broker._start("job", self.id, "preflight")
        return self.row()["record"]["quota_preparations"]["preflight"]
    def grant(self, prep):
        data = grant_data(allocation=prep["allocation"], phase_budget=prep["budget"], issued=self.now)
        return g.decode_grant(encoded(data))

    def test_reserve_bind_launch_and_receipt_commit_as_one_helper_fence(self):
        prep = self.prepare(); grant = self.grant(prep)
        self.broker._start("job", self.id, "preflight")
        self.assertEqual([], self.runner.starts)
        self.assertEqual(prep, self.row()["record"]["quota_preparations"]["preflight"])
        self.broker.bind_observation("job", self.id, "preflight", grant.wire)
        self.broker._start("job", self.id, "preflight")
        execution = self.runner.starts[-1][1]
        self.assertEqual(grant.as_dict(), self.runner.starts[-1][2]["quota_observation_grant"])
        self.assertIsNotNone(self.broker._guard_start(execution, lambda: True, stage="bootstrap"))
        proof = {"execution_id":execution,"unit":"lhj-"+hashlib.sha256((execution+":bootstrap").encode()).hexdigest()+".service",
            "state":"EXITED","exit_code":0,**dict.fromkeys(("future_start_blocked","tree_exited","collectors_stopped","writers_stopped","effects_checked"),True),
            "result":{"bootstrap_prepared":True}}
        with self.assertRaises(JobError): self.broker._guard_start(execution, lambda: self.fail("helper ran"), stage="helper", bootstrap_proof=proof)
        self.now += SECOND
        proof["result"]["quota_observation"] = observed(grant)
        self.assertTrue(self.broker._guard_start(execution,lambda:True,stage="helper",bootstrap_proof=proof))
        self.assertIsNone(self.broker._guard_start(execution,lambda:self.fail("replayed"),stage="helper",bootstrap_proof=proof))
        events = [e["kind"] for e in self.f.db.events("job",self.id)]
        self.assertEqual(["QUOTA_OBSERVED","BOOTSTRAP_COMPLETE","MANAGER_DELIVERY_INTENT"], events[-3:])
        with self.f.db.transaction() as tx:
            self.assertEqual(observed(grant), b.original(tx,self.f.db.get("job",self.id,tx),"preflight","QUOTA_OBSERVED","quota_observed")["observation"])
            self.f.db.update(tx,"job",self.id,"FAULT",{"quota_observed":{}})
            with self.assertRaises(JobError):b.original(tx,self.f.db.get("job",self.id,tx),"preflight","QUOTA_OBSERVED","quota_observed")
        view = self.broker.status(self.id, self.f.owner)
        self.assertFalse(any(key.startswith("quota_") for key in view))

    def test_restart_retains_reservation_without_launch_or_rebinding(self):
        prep = self.prepare(); grant = self.grant(prep)
        newer = Broker(self.f.db,self.f.policy,Registry(),self.runner,quota_required=True)
        with self.assertRaises(JobError): newer._start("job",self.id,"preflight")
        with self.assertRaises(ValueError): newer.bind_observation("job",self.id,"preflight",grant.wire)
        self.assertEqual(prep,self.row()["record"]["quota_preparations"]["preflight"])
        self.assertEqual([],self.runner.starts)

    def test_wrong_allocation_conflict_and_snapshot_damage_do_not_repair(self):
        prep = self.prepare(); grant = self.grant(prep)
        changed = grant.as_dict(); changed["request"]["request_id"] = "f"*32
        self.broker.bind_observation("job",self.id,"preflight",grant.wire)
        self.broker.bind_observation("job",self.id,"preflight",grant.wire)
        with self.assertRaises(ValueError): self.broker.bind_observation("job",self.id,"preflight",encoded(changed))
        with self.f.db.transaction() as tx:
            self.f.db.update(tx,"job",self.id,"FAULT",{"quota_bindings":{}})
        with self.assertRaises(JobError): self.broker.bind_observation("job",self.id,"preflight",grant.wire)

    def test_expired_original_preparation_cannot_receive_new_budget(self):
        prep = self.prepare(); self.now += 1000*SECOND
        with self.assertRaises(JobError): self.broker._start("job",self.id,"preflight")
        self.assertEqual(prep,self.row()["record"]["quota_preparations"]["preflight"])


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux nonblocking receipt collector')
class ManagerReceiptTests(unittest.TestCase):
    def test_piped_bootstrap_stop_targets_only_the_recorded_invocation(self):
        from pathlib import Path
        import subprocess
        from local_hand_jobs import runner
        manager=runner.SystemdManager({})
        for changed in (False,True):
            handle={'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    'invocation_id':'a'*32,'unit':'fixed-bootstrap.service','stage':'bootstrap',
                    'quota_pipe':b.Pipe(),'launch':mock.Mock(poll=lambda:None),'stop_acked':False}
            with mock.patch.object(manager,'_command',return_value=subprocess.CompletedProcess([],0,('b' if changed else 'a').encode()*32)) as command:
                manager._stop_unit(handle)
                self.assertEqual(not changed,handle['stop_acked'])
                if changed:self.assertEqual(1,command.call_count)
                else:command.assert_called_with('stop','--no-block','fixed-bootstrap.service')

    def test_real_pipe_client_exit_missing_eof_and_truncation(self):
        import subprocess
        import time
        from local_hand_jobs import runner
        grant=make_grant();packet=b.frame(observed(grant))
        for fault in (None,'truncated','no_eof'):
            with self.subTest(fault=fault):
                raw=packet[:-1] if fault=='truncated' else packet
                code='import os,time;os.write(1,'+repr(raw)+');'+('time.sleep(2)' if fault=='no_eof' else '')
                client=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
                os.set_blocking(client.stdout.fileno(),False)
                part={'quota_pipe':b.Pipe(),'quota_grant':grant,'launch':client,'pipe_nonblocking':True,'unit': 'fixed-bootstrap.service'}
                manager=runner.SystemdManager({})
                try:
                    with mock.patch.object(manager,'_command',return_value=subprocess.CompletedProcess([],0,b'')) as stop,\
                         mock.patch.object(budget,'current_clock',return_value={'boot_id':grant.request.as_dict()['boot_id'],'boottime_ns':2*SECOND}):
                        result=None;until=time.monotonic()+(0.15 if fault=='no_eof' else 2)
                        while time.monotonic()<until:
                            result=manager._bootstrap_receipt(part,{'ActiveState':'inactive'})
                            if result is not None or part['quota_pipe'].eof:break
                            time.sleep(.005)
                        if fault is None:self.assertEqual(grant.digest,result['grant_digest'])
                        else:self.assertIsNone(result)
                        if fault=='no_eof':self.assertFalse(part['quota_pipe'].eof)
                        stop.assert_called_once_with('stop','fixed-bootstrap.service')
                finally:
                    if client.poll() is None:client.kill()
                    client.wait(timeout=3);client.stdout.close()

    def test_three_units_expose_endpoint_only_to_bootstrap(self):
        from local_hand_jobs import runner
        grant=make_grant();data=grant.as_dict()
        manager=runner.SystemdManager({'slice':'synthetic.slice'})
        value={'budget_grant':data['budget'],'supervision_version':3,'quota_grant_digest':grant.digest,
               'quota_endpoint':data['endpoint']['path'],'writable':list(g.root_paths(data['allocation']).values())}
        for stage in ('bootstrap','helper','result_reader'):
            properties=manager._properties(value,stage)
            self.assertEqual('',properties['CapabilityBoundingSet'])
            self.assertEqual(stage!='bootstrap',value['quota_endpoint'] in properties['InaccessiblePaths'].split())
