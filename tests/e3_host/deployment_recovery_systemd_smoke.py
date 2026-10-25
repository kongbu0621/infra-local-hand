"""Opt-in real ordinary-user-systemd deployment protocol smoke test.

Runs only random temporary units/configurations. No daemon-reload, enable,
existing service changes, external requests, or Docker actions. The trusted
fixture Environment exercises real adapters and is deliberately distinct from
the production ConcreteEnvironment. Run explicitly with:

    python3 tests/e3_host/deployment_recovery_systemd_smoke.py --run-isolated-user-service

Requires Linux, a usable user systemd bus, and a local filesystem supporting
ordinary persistent file handles. The unit has a bounded maximum runtime, and
its stop/unlink cleanup runs even when assertions fail.
"""
import argparse
import copy, hashlib, json, os, socket, struct, sys, tempfile, time, uuid
from pathlib import Path
ROOT_TOOLS = str(Path(__file__).resolve().parents[2] / 'tools')
sys.path.insert(0, ROOT_TOOLS)
from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.model import PLAN_SCHEMA, digest, seal_plan
from admin.local_hand_deploy.store import Store
from admin.local_hand_deploy import files
from admin.local_hand_deploy.services import SystemdAdapter, definition_digest
from admin.local_hand_deploy.supervision import SupervisedRunner
from admin.local_hand_deploy.systemd_bus import SystemdBus
from local_hand_jobs.maintenance import MaintenanceGate
from local_hand_jobs import startup

# This harness supplies a fixed, trusted fixture environment. It is not a
# claim that the production ConcreteEnvironment or installed services ran.
HELPER='''import hashlib,json,os,socket,sys\nfrom pathlib import Path\nsys.path.insert(0, %r)\nfrom local_hand_jobs import startup\nfrom local_hand_jobs.maintenance import MaintenanceGate\np=Path(sys.argv[1]); raw=p.read_bytes(); config=json.loads(raw)\ngate=MaintenanceGate(config['gate'],config['node_id'],owner_uid=os.geteuid())\nproof={'component':'fixture','node_id':config['node_id'],'deployment_digest':config['deployment_digest'],'configuration_digest':hashlib.sha256(raw).hexdigest(),'payload_digest':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'entry':'local','pid':os.getpid(),'instance':startup.instance(os.getpid()),'invocation_id':os.environ['INVOCATION_ID'],'value':config['value']}\nserver=socket.socket(socket.AF_UNIX); address=config['socket']\ntry: os.unlink(address)\nexcept FileNotFoundError: pass\nwith startup.authorize(config,proof,gate):\n server.bind(address); server.listen(4)\nproof['protocol_ready']=True\nwhile True:\n connection,_=server.accept()\n with connection: connection.sendall(json.dumps(proof).encode()+b'\\n')\n''' % ROOT_TOOLS

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
 unit='lh-deploy-combined-'+uuid.uuid4().hex[:12]+'.service'
 unitroot=Path('/run/user')/str(os.geteuid())/'systemd/user'
 unitroot.mkdir(mode=0o700, parents=True, exist_ok=True)
 unitfile=unitroot/unit
 with tempfile.TemporaryDirectory(prefix='lh-deploy-combined-') as temp:
  root=Path(temp); uid=os.geteuid(); node='fixture-node'
  configpath=root/'selected.json'; helper=root/'listener.py'; helper.write_text(HELPER); helper.chmod(0o600)
  descriptor=root/'startup.json'; gatepath=root/'gate'; gatepath.mkdir(mode=0o700)
  socketpath=root/'listener.sock'; oldsrc=root/'old.json'; newsrc=root/'new.json'
  for value,source in [('old',oldsrc),('new',newsrc)]:
   source.write_text(json.dumps({'value':value,'node_id':node,'deployment_digest':digest(value),'gate':str(gatepath),'socket':str(socketpath),'maintenance':{'startup_descriptor':str(descriptor)}},sort_keys=True));source.chmod(0o600)
  configpath.write_bytes(oldsrc.read_bytes());configpath.chmod(0o600)
  gate=MaintenanceGate(gatepath,node,owner_uid=uid);gate.initialize(digest('old'),'bootstrap',bootstrap=True)
  def selection(source, deployment):
   return {'schema':startup.SCHEMA,'node_id':node,'deployment_digest':deployment,'decision_id':'bootstrap','mode':'stable','owner':None,'members':[{'path':str(configpath),'sha256':sha(source)},{'path':str(helper),'sha256':sha(helper)}],'components':{'fixture':{'configuration_digest':sha(source),'payload_digest':sha(helper),'entry':'local','running':True}},'permit':None}
  oldselection=selection(oldsrc,digest('old')); newselection=selection(newsrc,digest('new'))
  startup.publish(descriptor,oldselection,gate,expected_digest=None,owner_uid=uid)
  def loaded_probe(unitname):
   deadline=time.monotonic()+5
   while True:
    try:
     with socket.socket(socket.AF_UNIX) as conn:
      conn.settimeout(0.5);conn.connect(str(socketpath));peer=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12));data=b''
      while not data.endswith(b'\n'):
       data+=conn.recv(4096)
       if len(data)>16384:raise RuntimeError('oversized fixture proof')
     proof=json.loads(data)
     if peer[0]!=proof['pid'] or peer[1]!=uid or startup.instance(peer[0])!=proof['instance']:raise RuntimeError('fixture peer identity mismatch')
     return {**proof,'config_digest':proof['configuration_digest']}
    except (OSError,ValueError):
     if time.monotonic()>=deadline:raise
     time.sleep(.03)
  store=Store(root/'state',node);store.initialize()
  runner=SupervisedRunner(root/'calls',timeout=10)
  def guard_check(unitname,target):
   s=startup.read_selection(descriptor,owner_uid=uid);startup.verify_members(s,owner_uid=uid)
   g=gate.snapshot();c=s['components']['fixture']
   if s['mode']=='candidate' and (g['state']!='CLOSED' or g['owner']!=s['owner']):raise RuntimeError('wrong maintenance owner')
   return {'mode':s['mode'],'descriptor_digest':startup.digest(s),'config_digest':c['configuration_digest'],'deployment_digest':s['deployment_digest'],'target_running':c['running'],'boot':(s['permit'] or {}).get('boot_id'),'attempt_id':(s['permit'] or {}).get('attempt_id')}
  unitfile.write_text('[Unit]\nDescription=Temporary deployment protocol acceptance\nDefaultDependencies=no\n[Service]\nType=exec\nExecStart=/usr/bin/python3 '+str(helper)+' '+str(configpath)+'\nKillMode=control-group\nRestart=no\nRuntimeMaxSec=180s\n[Install]\nWantedBy=default.target\n');unitfile.chmod(0o600)
  try:
   with SystemdBus(user=True,timeout=5) as keeper:
    keeper.call('LoadUnit',(('s',unit),));keeper.call('RefUnit',(('s',unit),))
    keeper.run_job(unit,'StartUnit',lambda event:None)
    first=loaded_probe(unit)
    initial=keeper.unit(unit)
    deps=sorted(set(initial.get('Requires',[]))|set(initial.get('Wants',[]))|set(initial.get('Requisite',[])))
    profile={'manager':'user','units':{unit:{'policy_links':{},'hooks':{},'read_only_dependencies':deps,'inactive_conflicts':initial.get('Conflicts',[]),'restart_modes':['no']}}}
    adapter=SystemdAdapter(profile,runner,guard_check=guard_check,loaded_probe=loaded_probe)
    class Environment:
     def __init__(self):self.op=None
     def for_operation(self,op):self.op=op;return self
     def effect_key(self,step):return step['kind']+':'+step['action']['target']
     def preflight(self,op):
      actual=loaded_probe(unit);assert actual['deployment_digest']==op['plan']['source']['deployment_digest'];return {'passed':True}
     def prepare(self,step,op,record):
      if step['kind']=='file':
       staging=root/('stage-'+op['id']+'-'+step['id']);staging.mkdir(mode=0o700,exist_ok=True)
       return files.prepare_file(step['action'],staging,operation_id=op['id'],attempt_id='prepare',lock_fd=store.lock_fd)
      return copy.deepcopy(step['action'])
     def observe(self,step,prepared,attempt=None):
      if step['kind']=='file':
       result=files.observe_file(prepared);return {**result,'closed':True,'effective':result['state']=='target' and prepared['action']!='noop','synced':prepared['action']=='noop'}
      previous=attempt['binding'] if attempt and attempt.get('binding') else None
      result=adapter.observe_action(prepared,previous,lock_fd=store.lock_fd)
      return {**result,'state':result['outcome'],'effective':result['postcondition']}
     def execute(self,step,prepared,op,attempt_id,persist_intent,previous=None):
      if step['kind']=='file':
       result=files.execute_file(prepared,lock_fd=store.lock_fd);return {**result,'closed':True,'effective':prepared['action']!='noop','dispatched':True}
      prior=previous['binding'] if previous and previous.get('binding') else None
      result=adapter.execute(prepared,attempt_id=attempt_id,lock_fd=store.lock_fd,persist_intent=persist_intent,previous=prior)
      return {**result,'state':result['outcome'],'effective':result['postcondition']}
     def drain(self,op):return {'quiescent':not gate.active()}
     def selected_deployment(self,op):return op['plan']['target' if op['decision']=='COMMITTED' or op['direction']=='APPLY' else 'source']
     def publish(self,op,mode,attempt=None):
      s=copy.deepcopy(self.selected_deployment(op)['selection']);s['mode']=mode;s['owner']=None if mode=='stable' else op['id'];s['decision_id']=op['decision_id'] if mode=='stable' else None;s['permit']={'boot_id':startup.boot_id(),'attempt_id':attempt,'claims':{}} if mode=='candidate' else None
      current=startup.read_selection(descriptor,owner_uid=uid)
      return startup.publish(descriptor,s,gate,expected_digest=startup.digest(current),owner_uid=uid,maintenance_owner=op['id'] if mode=='stable' else None)
     def block_startup(self,op):return self.publish(op,'blocked')
     def candidate_startup(self,op,step,attempt_id):
      if step['action'].get('kind')=='service_start':return self.publish(op,'candidate',attempt_id)
     def check_local(self,op,rollback=False):
      selected=op['plan']['source' if rollback else 'target'];proof=loaded_probe(unit);actual=adapter.observe()['units'][unit]
      return {'passed':proof['deployment_digest']==selected['deployment_digest'] and proof['config_digest']==selected['selection']['components']['fixture']['configuration_digest'] and proof['pid']==actual['pid'] and proof['invocation_id']==actual['invocation_id'],'actual_invocation':proof['invocation_id']}
     def release_valid(self,op):return self.check_local(op,rollback=op['decision']!='COMMITTED')
     def publish_stable(self,op):return self.publish(op,'stable')
     def restored_plan(self,op,request):
      file_record=next(r for s,r in zip(op['plan']['steps'],op['steps']) if s['kind']=='file')
      return make_plan(request,op['plan']['target'],op['plan']['source'],file_record['prepared']['backup']['path'])
     def prepare_compensation(self,op):raise RuntimeError('fixture only accepts successful committed rollback successor')
    def make_plan(request,source,target,candidate):
     baseline=adapter.observe();original=baseline['units'][unit]
     actions=adapter.plan({unit:{'running':True,'policy':original['policy'],'definition_digest':original['definition_digest'],'config_digest':target['selection']['components']['fixture']['configuration_digest'],'deployment_digest':target['deployment_digest']}},baseline,_check_global=False)
     entry=files.plan_files([{'target':str(configpath),'source':str(candidate),'mode':0o600,'uid':uid,'gid':os.getegid()}])['files'][0]
     steps=[{'id':'stop','kind':'service','action':a} for a in actions if a['kind']=='service_stop']+[{'id':'config','kind':'file','action':entry}]+[{'id':'start','kind':'service','action':a} for a in actions if a['kind']=='service_start']
     return seal_plan({'schema':PLAN_SCHEMA,'request_id':request,'node_id':node,'source':source,'target':target,'steps':steps,'profile':{'test_only':'ordinary-user-service-no-reload'}})
    environment=Environment();coordinator=Coordinator(store,gate,environment)
    plan=make_plan('upgrade',{'deployment_digest':digest('old'),'selection':oldselection},{'deployment_digest':digest('new'),'selection':newselection},newsrc)
    applied=coordinator.apply(plan)
    if applied['decision']!='COMMITTED' or not applied['released']:raise RuntimeError(json.dumps({'apply_failed':applied['waiting'],'errors':applied['errors']}))
    second=loaded_probe(unit);assert second['value']=='new' and second['invocation_id']!=first['invocation_id']
    gate_sequence=gate.snapshot()['sequence'];again=coordinator.apply(plan);assert again==applied and loaded_probe(unit)['invocation_id']==second['invocation_id'] and gate.snapshot()['sequence']==gate_sequence
    rolled=coordinator.rollback(applied['id'])
    if rolled['decision']!='COMMITTED' or not rolled['released']:raise RuntimeError(json.dumps({'rollback_failed':rolled['waiting'],'errors':rolled['errors']}))
    third=loaded_probe(unit);assert third['value']=='old' and third['invocation_id']!=second['invocation_id'];seq=gate.snapshot()['sequence']
    repeated=coordinator.rollback(applied['id']);assert repeated==rolled and loaded_probe(unit)['invocation_id']==third['invocation_id'] and gate.snapshot()['sequence']==seq
    assert configpath.read_bytes()==oldsrc.read_bytes()
    print(json.dumps({'ordinary_user_systemd':True,'real_configuration_replace':True,'actual_listener_guard':True,'sqlite_coordinator':True,'apply':applied['decision'],'rollback_successor':rolled['decision'],'same_apply_no_restart':True,'same_rollback_no_restart':True,'original_bytes_restored':True,'final_gate':gate.snapshot()['state'],'three_distinct_invocations':len({first['invocation_id'],second['invocation_id'],third['invocation_id']})==3,'shared_daemon_reload':False,'live_services_touched':False},sort_keys=True))
    with SystemdBus(user=True,timeout=5) as ending:ending.run_job(unit,'StopUnit',lambda event:None)
    keeper.call('UnrefUnit',(('s',unit),))
  finally:
   try:
    with SystemdBus(user=True,timeout=5) as cleanup:cleanup.run_job(unit,'StopUnit',lambda event:None)
   finally:unitfile.unlink(missing_ok=True)
if __name__ == '__main__':
 parser = argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--run-isolated-user-service', action='store_true', required=True)
 parser.parse_args()
 main()
