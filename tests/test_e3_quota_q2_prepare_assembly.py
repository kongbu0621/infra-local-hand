"""Real policy/planner/SQLite assembly; host quota and service facts are modeled."""
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
from types import SimpleNamespace

ROOT = Path(__file__).parents[1]
PATH = ROOT / "tests/e3_host/q2_prepare_assembly.py"
spec = importlib.util.spec_from_file_location("q2_prepare_assembly_test", PATH)
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)


def host_module(name):
    path = ROOT / "tests/e3_host" / (name + ".py")
    spec = importlib.util.spec_from_file_location("_prepare_" + name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def facts(root="/synthetic-q2"):
    """Explicit synthetic OS facts, actual source file manifests and real policy inputs."""
    from local_hand_jobs import quota_grant as g
    root = str(root)
    checksum = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    source_files = {p.relative_to(ROOT).as_posix(): checksum(p) for folder in (ROOT / "tools", ROOT / "tests/e3_host")
                    for p in folder.rglob("*.py")}
    installed = {name.removeprefix("tools/"): value for name, value in source_files.items()
                 if name.split("/")[0] == "tools" and name.split("/")[1] in
                 ("local_hand", "local_hand_jobs", "local_hand_mcp", "local_hand_connect")}
    adminfiles = {name.removeprefix("tools/"): value for name, value in source_files.items() if name.startswith("tools/")}
    pin = lambda path, inode: dict(path=path, device=70, inode=inode)
    prog = {"python": dict(path=root + "/runtime/bin/python3", sha256="b"*64),
            "systemctl": dict(path="/usr/bin/systemctl", sha256="c"*64),
            "systemd_run": dict(path="/usr/bin/systemd-run", sha256="d"*64)}
    uid = max(1, os.getuid())
    gid = max(1, os.getgid())
    ident = dict(id="1"*32,authority_id="q2-authority",node_id="q2-node",
        install_uuid="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee", deployment_epoch=1,generation=1,
        operation_id="12345678-1234-4234-9234-123456789abc",profile_ref="q2-fixture",principal_id="q2-synthetic-fixture",
        epoch="5"*32,authority_digest="2"*64,manifest_digest="4"*64,slot_generation="6"*32,
        expires_at=1800000000,session="a"*64,ledger_id="q2-ledger")
    profile_roots = {role: root + "/quota/" + role for role in ("work", "evidence", "temporary")}
    roots = []
    def make_root(role, slot, index):
        path = root + "/quota/store" if slot == "store" else profile_roots[role] + "/slot-" + slot
        item = dict(path=path, role=role, device=71, inode=101+index, uid=uid, gid=gid, mode=0o40700,
            filesystem="ext4",filesystem_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",project_id=20001+index,
            xflags=512,hard_bytes=1024**2,hard_inodes=128,accounting=True,enforcement=True,identity_unchanged=True)
        roots.append(item)
        return item
    slots = [dict(slot_id="slot-"+letter, roots={role: make_root(role,letter,3*i+j)
        for j,role in enumerate(("work","evidence","temporary"))}) for i,letter in enumerate(("a","b"))]
    store=make_root("retained_store","store",6)
    parents={key:pin("/lhq"+key+".slice",400+i) for i,key in enumerate(("controller","query","management","supervisor"))}
    controller=lambda name, runtime:dict(schema="local-hand-q1-controller/v1",unit="lhq"+name+".service",
        cgroup=parents[name]["path"]+"/lhq"+name+".service",runtime_max_usec=runtime,timeout_stop_usec=1_000_000,
        memory_bytes=64*1024**2,tasks_max=32,cpu_quota_per_sec_usec=1_000_000,limit_cpu_seconds=runtime//1_000_000)
    budgets=dict(wall_seconds=72,terminate_grace_seconds=1,cpu_seconds=30,memory_bytes=64*1024**2,processes=8,
        temporary_bytes=1024**2,nas_bytes=0,log_bytes=32768*3,reservation_bytes=8*1024**2)
    capacity=dict(schema="local-hand-quota-capacity/v1",boot_id="11111111-2222-3333-4444-555555555555",
        epoch=ident["epoch"],authority_digest=ident["authority_digest"],domains=[dict(filesystem_uuid=r["filesystem_uuid"],
        project_id=r["project_id"],hard_bytes=r["hard_bytes"],hard_inodes=r["hard_inodes"]) for r in roots],
        ceiling_bytes=1024**3,ceiling_inodes=50000,retained_bytes=196*1024**2,retained_inodes=4096,
        management=dict(storage_bytes=32*1024**2,storage_inodes=1024,cpu_ns=400*10**9,memory_bytes=1024**3,pids=1024,output_bytes=16*1024**2))
    return dict(schema=a.SCHEMA,identity=ident,source=dict(root=root+"/source",commit="c"*40,files=source_files),
        installation=dict(package_root=root+"/runtime/lib/python3.12/site-packages",source_commit="c"*40,payload_digest="d"*64,
                          files=installed,programs=prog),
        admin=dict(programs=dict(prog,native=dict(path=root+"/native/quota_fd_query",sha256="e"*64)),
            entry=dict(path=root+"/source/tools/admin/local_hand_quota_observer/q2_entry.py",sha256=adminfiles["admin/local_hand_quota_observer/q2_entry.py"]),
            abi=dict(fsxattr_bytes=28,dqblk_bytes=72,qstatv_bytes=160),package_files=adminfiles),
        python_identity=dict(device=70,inode=900),ordinary=dict(uid=uid,gid=gid,initial_userns=dict(device=4,inode=5),
            parent=pin("/user.slice/user-"+str(uid)+".slice/user@"+str(uid)+".service/q2work.slice",450)),
        paths=dict(broker_root=root+"/broker",authority_root=root+"/authority",policy=root+"/authority/policy.json",
            profile_roots=profile_roots,forbidden_roots=[root+"/old-q1"],journal=pin(root+"/journal",501),
            management_evidence=pin(root+"/management-evidence",502),phase_outputs={phase:pin(root+"/"+phase+"-output",510+i) for i,phase in enumerate(a.PHASES)},
            endpoint_dir=root+"/control",launcher_output=pin(root+"/launcher-output",520),launcher_declarations=pin(root+"/launcher-declarations",521),
            supervisor_output=pin(root+"/supervisor-output",522),supervisor_declarations=pin(root+"/supervisor-declarations",523)),
        slots=slots,store=store,capacity=capacity,management=dict(receive_ns=10**9,stop_ns=10**9,storage_bytes=1024**2,
            storage_inodes=32,stages={stage:dict(cpu_ns=10**9,memory_bytes=16*1024**2,pids=4,output_bytes=32768,runtime_ns=10**9)
            for stage in g.STAGES},accept_ns=10**9,max_connections=4),
        controllers=dict(target=controller("controller",85_000_000),supervisor=controller("supervisor",100_000_000),
            controller_parent=parents["controller"],query_parent=parents["query"],management_parent=parents["management"],supervisor_parent=parents["supervisor"],
            target_storage_bytes=1024**2,target_storage_inodes=32,supervisor_storage_bytes=8*1024**2,supervisor_storage_inodes=32),
        setpriv=dict(path="/usr/bin/setpriv",sha256="f"*64),original_budgets=budgets,
        limits=dict(max_queued=1,max_running=1,retained_bytes=16*1024**2,ledger_emergency_bytes=65536,requests_per_minute=10))


class EntryTests(unittest.TestCase):
    def test_no_argument_entry_does_not_import_or_provision(self):
        run = subprocess.run([sys.executable,"-I","-B",str(PATH)],capture_output=True,timeout=10)
        self.assertEqual(3,run.returncode)
        self.assertEqual("BLOCKED",json.loads(run.stdout)["status"])
        self.assertEqual(b"",run.stderr)


@unittest.skipUnless(sys.platform.startswith("linux"), "Q2 Linux administrative assembly")
class AssemblyTests(unittest.TestCase):
    def test_real_user_manager_cgroup_path_preserves_lexical_rejections(self):
        from local_hand_jobs import quota_contract as q
        from admin.local_hand_quota_observer import admission
        path = "/user.slice/user-1001.slice/user@1001.service/q2work.slice"
        for validator in (q.canonical_path, admission.path):
            with self.subTest(validator=validator.__module__):
                self.assertEqual(path, validator(path))
                self.assertEqual("/sys/fs/cgroup" + path, validator("/sys/fs/cgroup" + path))
            for bad in ("/", "//user.slice", path + "/", path + "/../x", path + "/./x",
                        path + "//x", path + " x", path + "\nx", path + ";x", path + "$x",
                        path + "`x`", path + "\\x", path + "\0x", path + "*", path + "?", path + "é"):
                with self.subTest(validator=validator.__module__, bad=bad), self.assertRaises((q.QuotaError, admission.Rejected)):
                    validator(bad)

    def test_realistic_user_manager_peer_keeps_exact_credentials_and_cgroup(self):
        """Modeled /proc facts exercise the real peer admission with a real FD."""
        from admin.local_hand_quota_observer import q2_peer as peer
        from local_hand_jobs import quota_contract as q
        from test_e3_quota_q2_runtime import declaration, config
        value=declaration(); key=next(iter(value["peers"]))
        parent=value["peers"][key]["parent"]
        parent["path"]="/user.slice/user-1234.slice/user@1234.service/q2work.slice"
        grant=value["grants"][key];uid,gid=grant["roots"][0]["uid"],grant["roots"][0]["gid"]
        execution=grant["request"]["execution_id"]
        unit="lhj-"+hashlib.sha256((execution+":bootstrap").encode()).hexdigest()+".service"
        group=parent["path"]+"/"+unit
        cmd=b"/synthetic/python\0-I\0/synthetic/runner.py\0"
        value["peers"][key]["command_sha256"]=hashlib.sha256(cmd).hexdigest()
        with tempfile.TemporaryFile() as executable:
            info=os.fstat(executable.fileno())
            value["peers"][key]["executable"].update(device=info.st_dev,inode=info.st_ino)
            cfg=config(value)
            proc_stat=b"765 (ordinary) "+b" ".join([b"S"]+[b"0"]*18+[b"987"])
            status=(f"Uid: {uid} {uid} {uid} {uid}\nGid: {gid} {gid} {gid} {gid}\n"+
                "".join(name+": 0000000000000000\n" for name in ("CapInh","CapPrm","CapEff","CapBnd","CapAmb"))+
                "NoNewPrivs: 1\n").encode()
            observed={"stat":proc_stat,"cgroup":("0::"+group+"\n").encode(),"cmdline":cmd,
                "status":status,"environ":b"INVOCATION_ID="+b"a"*32+b"\0"}
            metadata=lambda filename: info if filename.endswith("/exe") else SimpleNamespace(st_dev=4,st_ino=999)
            with mock.patch.object(peer,"credentials",return_value=(765,uid,gid)), \
                 mock.patch.object(peer.os,"pidfd_open",side_effect=lambda *_:os.dup(executable.fileno())), \
                 mock.patch.object(peer.select,"poll",return_value=mock.Mock(poll=lambda _:[])), \
                 mock.patch.object(peer,"_fixed_read",side_effect=lambda path,_:observed[path.rsplit("/",1)[1]]), \
                 mock.patch.object(peer.os,"stat",side_effect=metadata), \
                 mock.patch.object(peer.c,"pinned_directory",side_effect=lambda pin:os.dup(executable.fileno())) as pinned, \
                 mock.patch.object(peer.c,"open_protected",side_effect=lambda _:os.dup(executable.fileno())), \
                 mock.patch.object(peer,"_boot_id",return_value=grant["request"]["boot_id"]):
                result=peer.inspect(cfg,object())
                self.assertEqual(group,result["cgroup"])
                self.assertEqual(parent,result["parent"])
                self.assertEqual("/sys/fs/cgroup"+parent["path"],pinned.call_args.args[0]["path"])
                observed["cgroup"]=("0::"+group.replace("user@1234", "user@1235")+"\n").encode()
                with self.assertRaisesRegex(q.QuotaError,"PEER_CGROUP"):peer.inspect(cfg,object())
                observed["cgroup"]=("0::"+group+"\n").encode()
                with mock.patch.object(peer,"credentials",return_value=(765,uid+1,gid)), \
                     self.assertRaisesRegex(q.QuotaError,"BOOTSTRAP_CREDENTIALS"):
                    peer.inspect(cfg,object())

    def test_real_policy_registry_chain_and_supervisor_decoders_agree(self):
        from local_hand_jobs.policy import Policy
        from admin.local_hand_quota_observer import q2_chain, q2_config
        value=facts(); before=copy.deepcopy(value)
        result=a.assemble(value)
        self.assertEqual(value,before)
        policy=Policy(result["policy"])
        chain_raw=a.encoded(result["chain"])
        chain=q2_chain.decode(chain_raw,hashlib.sha256(chain_raw).hexdigest())
        q2_chain.check_policy(chain,policy,value["identity"]["profile_ref"])
        supervisor=host_module("q2_supervisor"); launcher=host_module("q2_launcher")
        check=host_module("q2_fixture_check")
        template=copy.deepcopy(result["supervisor_template"])
        check.static_binding(template,supervisor,Path(value["source"]["root"]))
        for envelope in (template["supervisor_envelope"],template["launcher"]["controller_envelope"]):
            self.assertNotIn("issued_ns",envelope); self.assertNotIn("deadline_ns",envelope)
            self.assertFalse(a.DYNAMIC & set(envelope["controller"]))
            envelope.update(issued_ns=10**9,deadline_ns=10**9+envelope["controller"]["runtime_max_usec"]*1000)
        template["supervisor_envelope"]["controller"].update(invocation_id="a"*32,cgroup_device=70,cgroup_inode=999)
        binding=supervisor.validate(template,launcher,dict(boot_id=value["capacity"]["boot_id"],boottime_ns=2*10**9))
        self.assertEqual(100_000_000,binding["own"].runtime_max_usec)
        self.assertFalse(result["q2_accepted"])
        self.assertFalse(result["q3_accepted"])

    def test_actual_broker_allocator_matches_static_declarations_without_assembly_consuming(self):
        from local_hand_jobs.state import StateStore
        from local_hand_jobs import bootstrap_roots
        result=a.assemble(facts()); resident=result["resident"]
        with tempfile.TemporaryDirectory() as temp:
            os.chmod(temp,0o700)
            state=StateStore(Path(temp)/"jobs.sqlite","q2-authority","test-ledger",initialize=True)
            try:
                with state.transaction() as tx:
                    self.assertEqual([],state.all(tx))
                    row=state.insert(tx,"job",resident["request"]["operation_id"],resident["request"]["operation_id"],
                        resident["principal"]["principal_id"],resident["request"]["request_digest"],resident["request"],resident["plan"],resident["plan"]["reservation_bytes"])
                profile=result["policy"]["profiles"][resident["request"]["profile_ref"]]
                for phase in a.PHASES:
                    with state.transaction() as tx:
                        actual=bootstrap_roots.reserve(state,tx,row,phase,profile["bootstrap_slots"],extra_roots=
                            {"evidence_store":profile["bootstrap_evidence_store"]} if phase=="evidence" else None)
                    self.assertEqual(actual,result["chain"]["phases"][phase]["grant"]["allocation"])
            finally:state.close()

    def test_bad_root_budget_alias_extra_fields_and_program_binding_fail(self):
        from local_hand_jobs.contract import JobError
        for fault in ("extra","owner","domain","store-alias","temp-budget","four-root-budget","source","program","future-identity","parent","cleanup","missing-domain","outer-budget","output-alias","output-root-path","output-root-inode","ledger-id"):
            value=facts()
            if fault=="extra":value["arbitrary_command"]=["sh"]
            if fault=="owner":value["slots"][0]["roots"]["work"]["uid"]+=1
            if fault=="domain":value["store"]["project_id"]=value["slots"][0]["roots"]["work"]["project_id"]
            if fault=="store-alias":value["store"]["path"]=value["paths"]["profile_roots"]["work"]+"/store"
            if fault=="temp-budget":value["original_budgets"]["temporary_bytes"]=512*1024
            if fault=="four-root-budget":value["original_budgets"].update(reservation_bytes=3*1024**2,temporary_bytes=512*1024)
            if fault=="source":value["source"]["commit"]="b"*40
            if fault=="program":value["admin"]["programs"]["python"]=dict(path="/bad/python",sha256="a"*64)
            if fault=="future-identity":value["controllers"]["supervisor"]["invocation_id"]="a"*32
            if fault=="parent":value["controllers"]["supervisor_parent"]=copy.deepcopy(value["controllers"]["query_parent"])
            if fault=="cleanup":value["controllers"]["target"]["runtime_max_usec"]=99_000_000
            if fault=="missing-domain":value["capacity"]["domains"].pop()
            if fault=="outer-budget":value["capacity"]["management"]["cpu_ns"]=10**9*30
            if fault=="output-alias":value["paths"]["supervisor_output"]["inode"]=value["paths"]["launcher_output"]["inode"]
            if fault=="output-root-path":value["paths"]["supervisor_output"]["path"]=value["store"]["path"]+"/output"
            if fault=="output-root-inode":value["paths"]["supervisor_output"].update(device=value["store"]["device"],inode=value["store"]["inode"])
            if fault=="ledger-id":value["identity"]["ledger_id"]="x"*129
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError,JobError)):
                a.assemble(value)

    def test_empty_ledger_create_once_and_generation_is_real(self):
        if os.getuid()==0:
            maps=[[[int(x) for x in line.split()] for line in Path("/proc/self/"+name+"_map").read_text().splitlines()]
                  for name in ("uid","gid")]
            if not all(any(start <= 65534 < start+count for start,_,count in entries) for entries in maps):
                self.skipTest("65534 is not mapped in this executor; ordinary-credential ledger validation requires guest")
        with tempfile.TemporaryDirectory() as temp:
            value=facts(temp); broker=Path(value["paths"]["broker_root"]); broker.mkdir(mode=0o700)
            result=a.assemble(value)
            if os.getuid()==0:
                # A real ordinary child verifies the credential-sensitive core;
                # only disposable local files change owner, no account is made.
                uid=gid=65534
                result["policy"]["process_manager"]["uid"]=uid
                result["policy"]["local_peers"]={str(uid):value["identity"]["principal_id"]}
                profile=result["policy"]["profiles"][value["identity"]["profile_ref"]]
                for slot in profile["bootstrap_slots"]:
                    for root in slot["roots"].values():root["uid"]=uid
                profile["bootstrap_evidence_store"]["uid"]=uid
                os.chmod(temp,0o755);os.chown(broker,uid,gid)
                config=Path(temp)/"config.json";config.write_text(json.dumps(result["policy"]));os.chmod(config,0o644)
                script="""import importlib.util,json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
spec=importlib.util.spec_from_file_location('fixture_assembly',sys.argv[2])
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
cfg=json.loads(Path(sys.argv[3]).read_bytes())
r=a.initialize_ledger(cfg,'q2-ledger')
p=Path(r['path']);before=p.read_bytes()
try:a.initialize_ledger(cfg,'replacement')
except ValueError as e:assert str(e)=='PREP_LEDGER_CONSUMED'
else:raise AssertionError('replayed ledger')
assert p.read_bytes()==before
print(json.dumps(r))
"""
                run=subprocess.run([sys.executable,"-I","-B","-c",script,str(ROOT/"tools"),str(PATH),str(config)],
                    capture_output=True,timeout=10,user=uid,group=gid,extra_groups=[])
                self.assertEqual(0,run.returncode,run.stderr.decode())
                receipt=json.loads(run.stdout)
            else:
                receipt=a.initialize_ledger(result["policy"],"q2-ledger")
                before=Path(receipt["path"]).read_bytes()
                with self.assertRaisesRegex(ValueError,"PREP_LEDGER_CONSUMED"):
                    a.initialize_ledger(result["policy"],"replacement")
                self.assertEqual(before,Path(receipt["path"]).read_bytes())
            self.assertEqual([1,1],receipt["generation"])
            self.assertEqual(0o600,receipt["mode"])
