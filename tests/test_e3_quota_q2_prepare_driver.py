"""One-call bridge exercises real decoders and SQLite over modeled guest facts."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_e3_quota_q2_prepare_assembly import facts

PATH = Path(__file__).parent / "e3_host/q2_prepare_driver.py"
spec = importlib.util.spec_from_file_location("q2_prepare_driver_test", PATH)
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)


def fixture():
    f = facts()
    identities = {k:v for k,v in f["identity"].items() if k not in ("authority_digest", "manifest_digest")}
    controllers = {}
    for role in ("target", "supervisor"):
        controllers[role] = {k:v for k,v in f["controllers"][role].items() if k not in ("cgroup", "schema")}
        controllers[role].update({k: f["controllers"][role + "_" + k] for k in ("storage_bytes", "storage_inodes")})
    settings = dict(identity=identities, controllers=controllers, original_budgets=f["original_budgets"], limits=f["limits"],
        management=f["management"], capacity_management=f["capacity"]["management"],
        owner=dict(runtime_ns=120*10**9, storage_bytes=8*1024**2, storage_inodes=32, cpu_ns=10*10**9,
            memory_bytes=64*1024**2, pids=8, output_bytes=69632))
    directory_paths = {"state":f["paths"]["broker_root"], "authority":f["paths"]["authority_root"],
        "control":f["paths"]["endpoint_dir"], "journal":f["paths"]["journal"]["path"],
        "reservation":"/synthetic-q2/reservation", "capture":"/synthetic-q2/capture", "declarations":"/synthetic-q2/declarations",
        "session":"/synthetic-q2/session", "store_parent":"/synthetic-q2/store-parent"}
    directory_paths.update({"profile_"+k:v for k,v in f["paths"]["profile_roots"].items()})
    dirs = {role:dict(path=path, device=70, inode=1000+i, uid=f["ordinary"]["uid"] if role in
        ("authority","state","profile_work","profile_evidence","profile_temporary","store_parent") else 0,
        gid=f["ordinary"]["gid"], mode=0o40700) for i,(role,path) in enumerate(directory_paths.items())}
    roots=[]; planned=[]
    for slot in f["slots"]:
        for role,root in slot["roots"].items():
            value=dict(root, slot=slot["slot_id"][-1],ref="root"+str(root["project_id"]),inode_hard_limit=root["hard_inodes"])
            value.pop("hard_inodes"); roots.append(value)
    value=dict(f["store"],slot="store",ref="store",inode_hard_limit=f["store"]["hard_inodes"])
    value.pop("hard_inodes"); roots.append(value)
    for root in roots:
        planned.append({key:root[key] for key in ("ref","slot","role","path","project_id","hard_bytes","inode_hard_limit")})
    parents={role:dict(f["controllers"][role+"_parent"],unit="lhq"+role+".slice",uid=0,gid=0,mode=0o40755,
        memory_bytes=64*1024**2,tasks_max=32,cpu_quota_per_sec_usec=1000000)
        for role in ("query","management","controller","supervisor")}
    parents["ordinary"]=dict(f["ordinary"]["parent"],uid=f["ordinary"]["uid"],gid=f["ordinary"]["gid"],mode=0o40755)
    source=dict(f["source"],tree="f"*40)
    installation=dict(source=source,installed=f["installation"],admin=f["admin"],python_identity=f["python_identity"],ordinary_verified=True)
    host=dict(boot_id=f["capacity"]["boot_id"],initial_userns=f["ordinary"]["initial_userns"])
    observed=dict(host=host,mounts=dict(quota=dict(total_bytes=1024**3,available_bytes=900*1024**2,total_inodes=50000,free_inodes=49000)),
        ordinary=dict(name="syntheticq2",uid=f["ordinary"]["uid"],gid=f["ordinary"]["gid"]), roots=roots,parents=parents,
        directories=dirs,installation=installation,capacity_observed=dict(commitments={},quota_inventory=[
            dict(project=1001,hard=64*1024,ihard=4096)]),retained_before=["retained"],retained_after=["retained"])
    plan=dict(scope="LH-Q2-FIXTURE-PREP-v1",baseline="2ea59b8d1b262632bae5636938107ef2f002a59b",preparation_id="q2fixture001",
        settings=settings,candidate=dict(commit=f["source"]["commit"],tree=source["tree"]),account=observed["ordinary"],
        directories={key:dict(path=value["path"]) for key,value in dirs.items()},roots=planned,
        retained=[dict(path="/synthetic-q2/old-q1",device=70,inode=100)],retained_domains=[dict(project_id=1001,hard_bytes=64*1024**2,inode_hard_limit=4096)],
        mounts=dict(quota=dict(uuid=f["store"]["filesystem_uuid"])),tools=dict(setpriv=f["setpriv"]))
    return plan,dict(status="RESOURCES_PREPARED",facts=observed)


class ModelFiles:
    def __init__(self):
        self.writes={}; self.dirs={}; self.next=9000

    def directory(self,parent,name,mode=0o700):
        target=parent["path"]+"/"+name
        if target in self.dirs: raise FileExistsError(target)
        self.next+=1; value=dict(path=target,device=70,inode=self.next)
        self.dirs[target]=(value,mode)
        return value

    def write(self,parent,name,value,**kwargs):
        target=parent["path"]+"/"+name
        if target in self.writes: raise FileExistsError(target)
        self.writes[target]=(copy.deepcopy(value),kwargs)
        return dict(path=target,sha256=d.sha(d.encoded(value)))


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux receipt assembly")
class DriverTests(unittest.TestCase):
    def test_real_receipt_shapes_decode_through_policy_chain_and_handoff(self):
        from local_hand_jobs.state import StateStore
        from local_hand_jobs.policy import Policy
        plan,receipt=fixture(); files=ModelFiles(); commands=[]
        def command(args):
            commands.append(args)
            policy_path=args[args.index("--initialize-ledger")+1]
            config=files.writes[policy_path][0]; policy=Policy(config)
            with tempfile.TemporaryDirectory() as temporary:
                store=StateStore(Path(temporary)/"jobs.sqlite",policy.authority_id,plan["settings"]["identity"]["ledger_id"],initialize=True)
                try:
                    with store.transaction() as tx:
                        self.assertEqual([],store.all(tx))
                        generation=tx.execute("SELECT value FROM counters WHERE key='generation'").fetchone()[0]
                finally: store.close()
            return d.encoded(dict(path=config["broker_root"]+"/jobs.sqlite",device=70,inode=999,uid=plan["account"]["uid"],mode=0o600,
                ledger_id=plan["settings"]["identity"]["ledger_id"],generation=[policy.generation,generation]))
        prepared,invocation=d.complete(plan,receipt,files=files,command=command,
            clock=lambda:dict(boot_id=receipt["facts"]["host"]["boot_id"],boottime_ns=1000000000))
        self.assertEqual("PREPARED",prepared["status"]); self.assertFalse(prepared["q2_accepted"])
        self.assertEqual(1,len(commands)); self.assertIn("--bounding-set=-all",commands[0])
        handoff=files.writes[invocation[invocation.index("--plan")+1]][0]
        self.assertEqual(121000000000,handoff["owner_envelope"]["deadline_ns"])
        self.assertNotIn("issued_ns",handoff["template"]["supervisor_envelope"])
        self.assertEqual(0o700,files.dirs[handoff["declarations"]["path"]][1])
        self.assertEqual(0o700,files.dirs[handoff["template"]["declarations"]["path"]][1])
        self.assertEqual(0o755,files.dirs[handoff["template"]["launcher"]["declarations"]["path"]][1])
        self.assertEqual(plan["account"]["uid"],files.writes[prepared["policy"]["path"]][1]["owner"])
        chain=handoff["template"]["launcher"]["assembly"]
        self.assertEqual(8,len(chain["installation"]["capacity"]["domains"]))
        self.assertTrue(invocation[3].endswith("/q2_prepare_run.py"))
        runtime=d.helper("q2_prepare_run"); supervisor=d.helper("q2_supervisor"); launcher=d.helper("q2_launcher")
        issued=runtime.issue(handoff,supervisor,dict(boot_id=handoff["boot_id"],boottime_ns=1000000001))
        with mock.patch.object(runtime,"clock",return_value=dict(boot_id=handoff["boot_id"],boottime_ns=1000000002)):
            bound=runtime.binding(issued,supervisor,launcher)
        self.assertEqual(handoff["boot_id"],bound["boot_id"])
        with self.assertRaises(FileExistsError):
            d.complete(plan,receipt,files=files,command=lambda _:self.fail("ledger replay"),clock=lambda:self.fail("deadline renewed"))

    def test_bad_settings_fail_before_child_directory_creation(self):
        for fault in ("future_identity","too_long","zero_output","too_many_processes","short_cleanup","arbitrary_kind","capacity"):
            plan,receipt=fixture(); settings=plan["settings"]; files=ModelFiles()
            if fault=="future_identity": settings["identity"]["invocation_id"]="a"*32
            elif fault=="too_long": settings["owner"]["runtime_ns"]+=1
            elif fault=="zero_output": settings["management"]["stages"]["collector"]["output_bytes"]=0
            elif fault=="too_many_processes": settings["original_budgets"]["processes"]=65
            elif fault=="short_cleanup": settings["controllers"]["supervisor"]["runtime_max_usec"]=86000000
            elif fault=="capacity": settings["capacity_management"]["cpu_ns"]=1
            else: settings["kind"]="shell"
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                d.complete(plan,receipt,files=files,command=lambda _:self.fail("command reached"),clock=lambda:self.fail("clock reached"))
            self.assertFalse(files.dirs); self.assertFalse(files.writes)

    def test_root_reservations_rejected_before_directory_creation(self):
        plan,receipt=fixture(); files=ModelFiles()
        plan["roots"][2]["hard_bytes"]=2*1024**2
        with self.assertRaisesRegex(ValueError,"DRIVER_ROOT_BUDGET"):
            d.complete(plan,receipt,files=files,command=lambda _:self.fail("command reached"),clock=lambda:self.fail("clock reached"))
        self.assertFalse(files.dirs); self.assertFalse(files.writes)

    def test_real_provision_entry_rejects_unfunded_plan_before_reservation(self):
        from test_e3_quota_q2_prepare import ModelBackend, m
        from test_e3_quota_q2_prepare_contract import fixture as full_plan
        for fault in ("management_capacity", "root_budget"):
            plan=full_plan(); plan["settings"]=fixture()[0]["settings"]
            for root in plan["roots"]: root["hard_bytes"]=1024**2
            if fault=="management_capacity": plan["settings"]["capacity_management"]["cpu_ns"]=1
            else: plan["roots"][2]["hard_bytes"]=2*1024**2
            backend=ModelBackend()
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                m.prepare(plan,backend,validate_settings=lambda _:d.validate_plan(plan))
            self.assertEqual([],backend.calls)
            self.assertIsNone(backend.reservation)

    def test_observation_change_fails_without_ledger_or_handoff(self):
        for fault in ("account","root","source","unverified"):
            plan,receipt=fixture(); files=ModelFiles()
            if fault=="account": receipt["facts"]["ordinary"]["uid"]+=1
            elif fault=="root": receipt["facts"]["roots"][0]["hard_bytes"]+=4096
            elif fault=="source": receipt["facts"]["installation"]["source"]["commit"]="e"*40
            else: receipt["facts"]["installation"]["ordinary_verified"]=False
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                d.complete(plan,receipt,files=files,command=lambda _:self.fail("command reached"),clock=lambda:self.fail("clock reached"))
            self.assertFalse(files.writes)

    def test_ledger_failure_retains_preparation_without_owner_issuance(self):
        plan,receipt=fixture(); files=ModelFiles()
        def failed(_): raise RuntimeError("LEDGER_CHILD_FAILED")
        with self.assertRaises(RuntimeError):
            d.complete(plan,receipt,files=files,command=failed,clock=lambda:self.fail("deadline issued despite failure"))
        self.assertTrue(any(name.endswith("policy.json") for name in files.writes))
        self.assertFalse(any(name.endswith("handoff.json") for name in files.writes))
        self.assertFalse(any(name.endswith("prepared.json") for name in files.writes))

    def test_no_arguments_block_without_import_or_mutation(self):
        result=subprocess.run([sys.executable,"-I","-B",str(PATH)],capture_output=True,timeout=10)
        self.assertEqual(3,result.returncode); self.assertEqual("BLOCKED",json.loads(result.stdout)["status"])
        self.assertEqual(b"",result.stderr)


if __name__ == "__main__": unittest.main()
