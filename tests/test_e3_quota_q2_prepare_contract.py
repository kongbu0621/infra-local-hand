"""Pure explicit preparation contract: no host operations or acceptance."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).parent/"e3_host/q2_prepare_contract.py"
spec=importlib.util.spec_from_file_location("_prepare_contract_test",PATH)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
BOOT="11111111-2222-3333-4444-555555555555"


def fixture():
    mounts={role:dict(path="/synthetic/"+role,device=10+i,filesystem="ext4",source="/dev/test"+str(i),uuid=BOOT)
            for i,role in enumerate(("quota","system","journal","evidence"))}
    directories={}
    for role in m.DIRECTORY_ROLES:
        ordinary=role in ("state","authority","profile_work","profile_evidence","profile_temporary","store_parent")
        fs="quota" if role.startswith("profile_") or role=="store_parent" else "system"
        directories[role]=dict(path="/synthetic/"+fs+"/"+role,owner="ordinary" if ordinary else "root",
                              mode=0o755 if role in ("control","session","declarations") else 0o700,filesystem=fs)
    roots=[]
    for slot in ("a","b"):
        for role in ("work","evidence","temporary"):
            roots.append(dict(ref=slot+"_"+role,slot=slot,role=role,path=directories["profile_"+role]["path"]+"/slot-"+slot,
                              project_id=11001+len(roots),hard_bytes=4*1024**2,inode_hard_limit=128))
    roots.append(dict(ref="store",slot="store",role="retained_store",path=directories["store_parent"]["path"]+"/store",
                      project_id=11007,hard_bytes=4*1024**2,inode_hard_limit=128))
    return dict(schema=m.SCHEMA,purpose="ISOLATED_Q2_PREPARATION",scope=m.SCOPE,baseline=m.BASELINE,preparation_id="fixture001",
        host=dict(hostname="synthetic-guest",boot_id=BOOT,initial_userns=dict(device=4,inode=1),dmi_vendor="QEMU",dmi_product="KVM"),
        mounts=mounts,retained=[dict(path="/synthetic/old",device=10,inode=2)],
        retained_domains=[dict(project_id=10001,hard_bytes=64*1024**2,inode_hard_limit=4096)],
        account=dict(name="sample",uid=1100,gid=1100),directories=directories,roots=roots,
        parents={role:dict(unit="lhq"+role+".slice",memory_bytes=256*1024**2,tasks_max=32,cpu_quota_per_sec_usec=1000000)
                 for role in (*m.SYSTEM_PARENTS,"ordinary")},
        candidate=dict(source="/synthetic/input/source",commit="a"*40,tree="b"*40,wheel="/synthetic/input/candidate.whl",
                       wheel_sha256="c"*64,destination="/synthetic/system/installation"),
        tools={role:dict(path="/synthetic/bin/"+role,sha256="d"*64) for role in m.TOOLS},
        budgets=dict(**m.CEILINGS,installation_inodes=8192,state_inodes=1024,journal_inodes=1024,capture_inodes=1024,
                     preparation_seconds=300,command_seconds=15,command_output_bytes=32768,retained_scan_bytes=256*1024**2,
                     retained_scan_entries=8192),settings={"explicit_settings_test":True})


def decode(value):
    raw=m.encoded(value); return m.decode(raw,hashlib.sha256(raw).hexdigest())


class PreparationContract(unittest.TestCase):
    def test_valid_contract_has_exact_seven_fresh_domains(self):
        v=fixture(); self.assertEqual(v,decode(v)); self.assertEqual(7,len(v["roots"]))

    def test_unknown_and_wrong_scope_fail(self):
        for key,value in (("unknown",1),("scope","OTHER"),("baseline","a"*40)):
            v=fixture(); v[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):decode(v)

    def test_duplicate_and_invalid_json_fail(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":1.1}',b'{"a":NaN}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):m.document(raw)

    def test_budget_ceiling_and_boolean_amount_rejected(self):
        for group,key,value in (("budgets","installation_bytes",257*1024**2),("budgets","preparation_seconds",601),
                                ("budgets","command_output_bytes",32769),("account","uid",True)):
            v=fixture(); v[group][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):decode(v)

    def test_project_reuse_and_wrong_role_rejected(self):
        for field,value in (("project_id",10001),("project_id",11002),("role","retained_store"),("hard_bytes",65*1024**2)):
            v=fixture();v["roots"][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):decode(v)

    def test_new_paths_cannot_alias_or_overlap_old_paths(self):
        for path in ("/synthetic/old/new","/synthetic/old","/synthetic/system/state","/synthetic/input/source/new"):
            v=fixture();v["candidate"]["destination"]=path
            with self.subTest(path=path),self.assertRaises(ValueError):decode(v)

    def test_parent_alias_and_mount_alias_rejected(self):
        v=fixture();v["parents"]["query"]["unit"]=v["parents"]["controller"]["unit"]
        with self.assertRaises(ValueError):decode(v)
        v=fixture();v["mounts"]["system"]["device"]=v["mounts"]["quota"]["device"]
        with self.assertRaises(ValueError):decode(v)

    def test_paths_reject_traversal_and_allow_real_manager_name(self):
        for path in ("//tmp/a","/tmp/../a","relative","/"):
            with self.subTest(path=path),self.assertRaises(ValueError):m.path(path)
        self.assertEqual("/user.slice/user-1100.slice/user@1100.service/lhqordinary.slice",
                         m.path("/user.slice/user-1100.slice/user@1100.service/lhqordinary.slice"))

    def test_ordinary_authority_and_control_access_modes(self):
        for role,mode in (("authority",0o755),("control",0o700),("declarations",0o700)):
            v=fixture();v["directories"][role]["mode"]=mode
            with self.subTest(role=role),self.assertRaises(ValueError):decode(v)


if __name__=="__main__":unittest.main()
