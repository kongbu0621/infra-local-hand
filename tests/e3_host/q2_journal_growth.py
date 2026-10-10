import argparse
import os
from pathlib import Path
import re
import resource
import selectors
import shlex
import stat
import subprocess
import sys
import time
import base64
import errno
COMMANDS=[]
VM_LIMITS=None
if __package__ in (None,""):
 sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from e3_host import q2_core_capacity_capture as prior
from e3_host import q2_core_prior_attempt as history
from e3_host import q2_journal_retained_fds as custody
from e3_host.q2_journal_growth_guest import ProcessIdentity
from e3_host.q2_journal_growth_guest import (identity,stable_identity,validate_file,
write_all,hash_fd,proc_start,proc_bytes,growth_descriptor,bind_window,
control_limits,guest_startup_assurance,validate_startup_assurance,REPORT_SCHEMA)
local=prior.local
require,canonical,digest=prior.require,prior.canonical,prior.digest
R="10d2a5c827964989f41ca6e8eeac3d44de6d0f04"
A="59948ec4fedb807a31cdbff77acc134e84414160"
C="6493b1ae035dfa852952165046417c78f0f5383c"
READ_A="2b4448c7b89d1910840f7aee2ae2b781f970e179"
READ_C="b5414d0cfd505b220ba4b68a454202f245c77f6c"
TERM_A="2b236865dc0a89e475c4021cac44d7193f252f67"
TERM_C="12f7acac3b09fc5bd9344473ec930646c87e0f59"
DR_A="ef46ac169fd9084875cb5c5148a9c4985ace680c"
DR_C="65026c8c7722bc487c317d392b50b017a7350dee"
DRV2_A="4341487c9be9ef64cf6fccbd973ed438a66e7483"
DRV2_C="807d61b75841a416064f4c1ec1d7c2e0187e0d49"
MB_A="d18b490a7cdb63ee43044a29a89746ef78fccff3"
MB_C="3d928a323d1aad12c20a66594bb295d4df14fab0"
WORK_A="42a66be98c45e817e866d3fb86a1c184c2ce55f9"
WORK_C="1f656f7dab12ddb02c6927d3fc08c2fbe81ffebc"
DRIFT_A="4f2a6a37ad5afd027dbde0f1656a3552750cb3b2"
DRIFT_C="e13f8efcb8dee4e4280dd722f7836ea94a27b83b"
MINIMAL_A="5d6cefa602e9146f02887ebfaa4b0cad4e376ff2"
MINIMAL_C="8a4c24cefe4abbab193577b2dff48fc49626cae4"
SERIAL_A=history.c.SERIAL_BASELINE["commit"]
SERIAL_C=history.c.SERIAL_CLOSURE["commit"]
SYSTEMCTL_A=history.c.SYSTEMCTL_BASELINE["commit"]
SYSTEMCTL_C=history.c.SYSTEMCTL_CLOSURE["commit"]
TEMPLATE_A=history.c.TEMPLATE_BASELINE["commit"]
TEMPLATE_C=history.c.TEMPLATE_CLOSURE["commit"]
NAMES_A=history.c.NAMES_BASELINE["commit"]
NAMES_C=history.c.NAMES_CLOSURE["commit"]
EXEC_A=history.c.EXEC_BASELINE["commit"]
EXEC_C=history.c.EXEC_CLOSURE["commit"]
GS_A=history.c.GS_BASELINE["commit"]
GS_C=history.c.GS_CLOSURE["commit"]
QI_A=history.c.QI_BASELINE["commit"]
QI_C=history.c.QI_CLOSURE["commit"]
DS_A=history.c.DS_BASELINE["commit"]
DS_C=history.c.DS_CLOSURE["commit"]
VM_A=(history.c.VM_ADOPTION_BASELINE or {}).get("commit")
VM_C=(history.c.VM_ADOPTION_CLOSURE or {}).get("commit")
RT_A=history.c.RUNTIME_BASELINE["commit"]
RT_C=history.c.RUNTIME_CLOSURE["commit"]
FD_A=history.c.HOST_FD_BASELINE["commit"]
FD_C=history.c.HOST_FD_CLOSURE["commit"]
UC_A=history.c.USAGE_BASELINE["commit"]
UC_C=history.c.USAGE_CLOSURE["commit"]
TC_A=history.c.TRANSPORT_BASELINE["commit"]
TC_C=history.c.TRANSPORT_CLOSURE["commit"]
RC_A=history.c.RESUMED_VM_BASELINE["commit"]
RC_C=history.c.RESUMED_VM_CLOSURE["commit"]
ACCESS_MODE="TRUSTED_SINGLE_ADMIN"
MINIMAL_PINS=("f132068c02f6a49332e991525591c409d38690bb1cbff51d0f17de1e68e28769",
"121f67c11bbc85e18aed7635f3541cdb581fdb52aceba25fb12aca18aecf760b",
"093e0daac0f85cc78a48fcf58386d3133cfc796e9faba416b622dd0e072b8c58")
DRIFT_REPAIR="711932aae3370c7f2ed5c1a51ac82d3b0f67a6e5"
DRIFT_PINS=("1b176e044cfb4bf4dc4d7e6d7cee01e1480e3acf67825c9eda78980bf71d577f",
"473ace5e05c300f1e6751d97727b04e69f7f53628f3220d06bfdb1483e77551a",
"aec1a315f47fb05b5ccdc2a0855f5de479489d13c5e80f3d2e294a3563c920be")
WORK_PINS=("632aeecb163ad6e496a917fd73f9230aca1144d1e91050c78c8abff2b4d5ae38",
"52d75a0c689ae1ed5321a2b5fde5061084fd05c267cac9cf012924a97eac2e96",
"ec8f299e7cd9d9c0fc10eaa34e0ff75b0276fc2c863b753d4f8c109d7fc025b2")
MB_PINS=("868f86ddb157a693aa4ae29267b6d65434dac0c3656b08c94b10d86476974b12",
"6d6d455a38666287bf886a39ccf0f0756f4ca34020bd3c00b7b3b139886fcc41",
"92fda90f23db943cbafb241c5579ecab53da223b2120f8777908ebf5ae20679f")
DRV2_PINS=("a4a7891c01d32abf7a3283a39a0bf701cd47d023bab14808bf25f84ef98eca5b",
"a17ef97537748d03b0d48bc9e6945785fbda6d707875ad925df773fa9c511bbb",
"13f2ae38d9637c3e3d96cd59216037da7569132fa73bb4187e30a49763967c67")
DR_PINS=("bccfd1d244bcd250a4c9c5c1fdb4aad4401d5398f0e9c3939d5b7ab0257d27d6",
"72cee2ad2ce82fa47bd8a40dc8e3e74da5de1ea9e8674d22c3c82df8cd04b543",
"74eb2b9c8c45b159131af785ce14976b104923411b307b8f3d4f7269124d6692")
READ_PINS=("0eabd193b89131f701bf53f25e2426fb36d58df8c03e48ba50ab0d0fe5982fd5",
"6fe0fe118bbdd070773e1d9af9be7aed0da9256cdb5b21126b6b4d0d87e85b0f",
"7d57fa9d5003e53672abd7ac273ab1dd0fc728cff8044639a14d49f269d01300")
SESSION="lhqjgrow-20261010c"
MIB=1048576
OLD_SIZE,NEW_SIZE=256*MIB,512*MIB
BACKUP_CAP,IMAGE_CAP,CAPTURE_CAP=320*MIB,576*MIB,8*MIB
HOST_BYTES,HOST_INODES=19441*MIB,5582
# Additional host descriptors from preflight through receipt: post transport
# peaks at 17 (9 retained outputs/pidfd, selector, 7 Popen descriptors).
# Three more slots cover bounded identity/usage reads. This is admission only;
# it neither releases a retained identity nor makes a consumed window reusable.
HOST_FD_LIMIT,HOST_FD_RESERVE=128,20
def host_fd_admission(fd,check,stage):
 check()
 reserved=[]
 available=0
 try:
  for _ in range(HOST_FD_RESERVE):
   duplicate=os.dup(fd)  # Same held directory; no new source/path observation.
   reserved.append(duplicate)
   if duplicate>=HOST_FD_LIMIT:
    raise OSError(errno.EMFILE,"host descriptor admission")
   available+=1
 except OSError as error:
  if error.errno!=errno.EMFILE:
   raise
  failure=prior.r.ObservationError("GROWTH_HOST_FD_BUDGET")
  failure.diagnostic=dict(operation="host_fd_admission",stage=stage,
descriptor_limit=HOST_FD_LIMIT,required_free=HOST_FD_RESERVE,
available_below_limit=available)
  raise failure from error
 finally:
  for duplicate in reserved:
   os.close(duplicate)
 check()
STATES=("LOCAL_CHECKED","CONSUMED","GUEST_QUIET","POWERED_OFF",
"BACKED_UP","IMAGE_GROWN","BOOTED","FILESYSTEM_GROWN","VERIFIED")
SUFFIXES=("consumed.json","events.jsonl","pre.stdout","pre.stderr","post.stdout",
"post.stderr","receipt.json","vm.pid","journal.backup.qcow2")
NAMES={suffix:"."+SESSION+"."+suffix for suffix in SUFFIXES}
DOC_PINS={
"REQUIREMENTS.md":"93ac5383bb1823086dc0546fb4eebcf1f70ffd7e7a824247b3f6c9e210417f4d",
"ARCHITECTURE.md":"5b703c51afab91676851af1bcaf4464469ea2183f7bd5dbc79d120a1efcc6f28",
"IMPLEMENTATION_PLAN.md":"aa3c04b8fce9a914dd7009644ac0a3a853a8d4f38de8f85b73a0d644dd723e60",
}
CAPACITY_PINS={
"consumed.json":(939,"537f3f93f47034ae253c735052cbae443eea3aa3f775849698830e4b26cec9ff"),
"stdout":(3609,"00cc8b744b8d63bf7d83a4044921fc1a80b7a21b289cf62b4e6f33cd9548b8db"),
"stderr":(0,"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
"receipt.json":(1807,"575e74006d530fd562a67d66d5ce066a8e941d914da1f84bec2eb839b7ee4270"),
}
class Window(local.Deadline):
 def remaining(self,limit=900):
  return super().remaining(limit)
 def change(self):
  self.remaining(780)
class Sequence:
 def __init__(self,check,record):
  self.state="LOCAL_CHECKED"
  self.check,self.record=check,record
  self.started=set()
 def step(self,target,effect):
  require(self.state in STATES and target in STATES and
STATES.index(target)==STATES.index(self.state)+1,
"GROWTH_SEQUENCE")
  require(target not in self.started,"GROWTH_NO_RETRY")
  self.started.add(target)
  try:
   self.check()
   self.record(dict(step=target,state="STARTED"))
   result=effect()
   self.check()
   self.record(dict(step=target,state="RETURNED",result=result))
   self.state=target
   return result
  except BaseException:
   self.state="STOP_AND_RETAIN"
   raise
class Store:
 def __init__(self,fd,check):
  self.fd,self.check=fd,check
  self.owner=os.geteuid()
  self.opened={}
 def absent(self):
  for name in NAMES.values():
   try:
    os.stat(name,dir_fd=self.fd,follow_symlinks=False)
   except FileNotFoundError:
    continue
   raise prior.r.ObservationError("GROWTH_OUTPUT_EXISTS")
 def capacity(self):
  self.check()
  value=os.fstatvfs(self.fd)
  require(value.f_bavail*value.f_frsize>=HOST_BYTES and value.f_favail>=HOST_INODES,
"GROWTH_HOST_CAPACITY")
 def create(self,suffix):
  require(suffix in NAMES and suffix not in self.opened,"GROWTH_OUTPUT_NAME")
  self.check()
  fd=os.open(NAMES[suffix],os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW
|os.O_CLOEXEC|os.O_NOATIME,0o600,dir_fd=self.fd)
  self.opened[suffix]=fd
  require(stat.S_IMODE(os.fstat(fd).st_mode)==0o600,"GROWTH_OUTPUT_MODE")
  os.fsync(self.fd)
  return fd
 def budget(self):
  logical=allocated=count=0
  for suffix,fd in self.opened.items():
   info=os.fstat(fd)
   require(stable_identity(info)==stable_identity(os.stat(NAMES[suffix],dir_fd=self.fd,
follow_symlinks=False)),"GROWTH_OUTPUT_DRIFT")
   cap=BACKUP_CAP if suffix=="journal.backup.qcow2" else CAPTURE_CAP
   validate_file(info,cap,self.owner)
   if suffix!="journal.backup.qcow2":
    count+=1
    logical+=info.st_size
    allocated+=info.st_blocks*512
  require(max(logical,allocated)<=CAPTURE_CAP and count<=32,"GROWTH_CAPTURE_BUDGET")
  return dict(logical_bytes=logical,allocated_bytes=allocated,inodes=count)
 def put(self,suffix,raw):
  require(type(raw) is bytes and len(raw)<=(MIB if suffix.endswith(("stdout","stderr"))
else 65536),"GROWTH_OUTPUT_LIMIT")
  fd=self.create(suffix)
  write_all(fd,raw,self.check)
  os.fsync(fd)
  self.budget()
  return fd
 def event(self,value):
  raw=canonical(value)
  require(len(raw)<=65536,"GROWTH_EVENT_LIMIT")
  fd=self.opened.get("events.jsonl")
  if fd is None:
   fd=self.create("events.jsonl")
  require(os.fstat(fd).st_size+len(raw)<=MIB,"GROWTH_EVENTS_LIMIT")
  write_all(fd,raw,self.check)
  os.fsync(fd)
  self.budget()
 def close(self):
  for fd in self.opened.values():
   os.close(fd)
  self.opened.clear()
def full_backup(store,source_fd):
 store.capacity()
 before=os.fstat(source_fd)
 validate_file(before,BACKUP_CAP,os.geteuid())
 source_digest=hash_fd(source_fd,BACKUP_CAP,store.check)
 target=store.create("journal.backup.qcow2")
 os.lseek(source_fd,0,os.SEEK_SET)
 count=0
 while count<before.st_size:
  store.check()
  raw=os.read(source_fd,min(65536,before.st_size-count))
  require(raw,"GROWTH_BACKUP_SHORT_READ")
  write_all(target,raw,store.check)
  count+=len(raw)
  store.budget()
 os.fsync(target)
 require(stable_identity(os.fstat(source_fd))==stable_identity(before),"GROWTH_BACKUP_DRIFT")
 copied_digest=hash_fd(target,BACKUP_CAP,store.check)
 require(copied_digest==source_digest and os.fstat(target).st_ino!=before.st_ino,
"GROWTH_BACKUP_MISMATCH")
 store.budget()
 store.capacity()
 return copied_digest
def qemu_argv(start,anchor,serial,*,activation=None):
 require(digest(start)==local.PINS["start.sh"][1],"GROWTH_START_PIN")
 require(re.fullmatch(r"/[A-Za-z0-9_./-]+",anchor) and os.path.normpath(anchor)==anchor,
"GROWTH_ANCHOR")
 text=start.decode("utf-8","strict")
 require("q1_vm="+anchor+"\n" in text,"GROWTH_START_ANCHOR")
 pieces=text.split("\nqemu-system-x86_64 \\\n")
 require(len(pieces)==2,"GROWTH_START_FORMAT")
 command=pieces[1].split("\n\n",1)[0].replace("\\\n"," ")
 args=shlex.split(command)
 require(all(arg.isascii() for arg in args),"GROWTH_START_ENCODING")
 args=[arg.replace("$q1_vm",anchor).replace("$q1_log",serial) for arg in args]
 require(not any("$" in arg or "`" in arg for arg in args),"GROWTH_START_EXPANSION")
 require(args.count("-pidfile")==args.count("-serial")==1 and
args[args.index("-pidfile")+1]==anchor+"/vm.pid" and
args[args.index("-serial")+1]=="file:"+serial,"GROWTH_START_OUTPUT")
 original=["qemu-system-x86_64",*args]
 if activation is not None:
  history.validate_vm_activation(activation)
  require(serial==activation["serial"],"GROWTH_ACTIVATION_SERIAL")
  original[original.index("-pidfile")+1]=activation["pidfile"]
  system=[i+1 for i,word in enumerate(original[:-1]) if word=="-drive"
 and original[i+1]=="if=none,id=os,format=qcow2,file="+anchor+"/system.qcow2"]
  require(len(system)==1,"GROWTH_ACTIVATION_SYSTEM_ARGUMENT")
  original[system[0]]="if=none,id=os,format=qcow2,file="+activation["system_path"]
  require(digest(b"\0".join(word.encode("ascii") for word in original)+b"\0")
 ==activation["vm"]["argv_sha256"],"GROWTH_ACTIVATION_ARGV")
 new=original.copy()
 new[new.index("-pidfile")+1]=anchor+"/"+NAMES["vm.pid"]
 new[new.index("-serial")+1]="null"
 require(sum(a!=b for a,b in zip(original,new))==2,"GROWTH_START_DELTA")
 return original,new
def image_commands(path,backup):
 return dict(info=["info","--output=json","-f","qcow2",path],
check=["check","--output=json","-f","qcow2",path],
resize=["resize","-f","qcow2",path,str(NEW_SIZE)],
compare=["compare","-f","qcow2","-F","qcow2",backup,path])
def validate_image_info(raw,expected_size):
 value=prior.r.parse(raw,65536)
 require(expected_size in (OLD_SIZE,NEW_SIZE) and value.get("format")=="qcow2"
and value.get("virtual-size")==expected_size and not value.get("encrypted",False)
and not value.get("snapshots") and not value.get("backing-filename")
and not value.get("full-backing-filename"),"GROWTH_IMAGE_INFO")
 data=value.get("format-specific",{}).get("data",{})
 require(data.get("compat")=="1.1" and data.get("corrupt") is False
and not data.get("bitmaps") and not data.get("encrypt"),"GROWTH_IMAGE_FEATURES")
 return value
def vm_limits():
 os.umask(0o077)
 if VM_LIMITS is not None:
  for key,limits in VM_LIMITS.items():
   resource.setrlimit(key,limits)
class Command:
 def __init__(self,argv,check,*,executable=None,pass_fds=(),limit=MIB,limits=True,
stderr_limit=None):
  require(0<limit<=MIB,"GROWTH_STREAM_CAP")
  check()
  self.check=check
  self.caps=dict(stdout=limit,stderr=limit if stderr_limit is None else stderr_limit)
  require(all(type(n) is int and 0<n<=limit for n in self.caps.values()),"GROWTH_STREAM_CAP")
  self.process=subprocess.Popen(argv,executable=executable,pass_fds=pass_fds,
stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
env={"PATH":"/usr/sbin:/usr/bin:/bin","LANG":"C","LC_ALL":"C"},
preexec_fn=control_limits if limits else vm_limits,start_new_session=True)
  self.is_vm=not limits
  COMMANDS.append(self)
  self.identity=dict(pid=self.process.pid,argv_sha256=digest(canonical(argv)),starttime=None)
  try:
   self.identity["starttime"]=proc_start(proc_bytes(self.process.pid,"stat",16384,lambda:None))
  except (OSError,RuntimeError,ValueError):
   pass
  self.output={"stdout":bytearray(),"stderr":bytearray()}
  self.eof={"stdout":False,"stderr":False}
  self.selector=selectors.DefaultSelector()
  for name in self.output:
   stream=getattr(self.process,name)
   os.set_blocking(stream.fileno(),False)
   self.selector.register(stream,selectors.EVENT_READ,name)
 def collect(self):
  try:
   while self.selector.get_map() or self.process.poll() is None:
    self.check()
    for key,_ in self.selector.select(0.05):
     name=key.data
     raw=os.read(key.fileobj.fileno(),min(65536,self.caps[name]+1-len(self.output[name])))
     if not raw:
      self.eof[name]=True
      self.selector.unregister(key.fileobj)
     else:
      self.output[name].extend(raw)
      require(len(self.output[name])<=self.caps[name],"GROWTH_STREAM_LIMIT")
     self.check()
   self.check()
   return dict(returncode=self.process.returncode,eof=self.eof.copy(),
**{name:bytes(value) for name,value in self.output.items()})
  finally:
   self.selector.close()
   for name in self.output:
    getattr(self.process,name).close()
def run_tool(argv,check,**kwargs):
 command=Command(argv,check,**kwargs)
 try:
  result=command.collect()
 except BaseException as error:
  error.growth_command=command
  raise
 if result["returncode"]!=0 or not all(result["eof"].values()):
  error=prior.r.ObservationError("GROWTH_TOOL_FAILED")
  error.growth_command,error.growth_result=command,result
  raise error
 return result
class Tool:
 def __init__(self,path,check):
  self.path,self.check=path,check
  self.fd,self.info=local.bound_executable(path)
  require(os.fstat(self.fd).st_nlink==1,"GROWTH_TOOL_LINK")
  try:
   result=self.run(["--version"])
   self.version=result["stdout"]+result["stderr"]
   require(0<len(self.version)<=16384,"GROWTH_TOOL_VERSION")
  except BaseException:
   self.close()
   raise
 def recheck(self):
  self.check()
  parent=local.open_directory(str(Path(self.path).parent),0)
  try:
   current=os.stat(Path(self.path).name,dir_fd=parent,follow_symlinks=False)
   require(local.metadata(current)==self.info==local.metadata(os.fstat(self.fd))
and current.st_nlink==1,"GROWTH_TOOL_DRIFT")
  finally:
   os.close(parent)
 def run(self,args,*,vm=False):
  self.recheck()
  name="qemu-system-x86_64" if vm else self.path
  require(not vm or self.path=="/usr/bin/qemu-system-x86_64","GROWTH_VM_TOOL")
  result=run_tool([name,*args],self.check,executable=f"/proc/self/fd/{self.fd}",
pass_fds=(self.fd,),limits=not vm)
  self.recheck()
  return result
 def binding(self):
  self.recheck()
  value=dict(path=self.path,identity=self.info,version_sha256=digest(self.version))
  return value|dict(binding_sha256=digest(canonical(value)))
 def close(self):
  if self.fd is not None:
   os.close(self.fd)
   self.fd=None
GROWTH_FRAME_PIN=(5496087,"c9f4bb2744d48f9e7174157a95761d081be038cf4dd4f67ae42620a1a9e6d315")
GROWTH_CARRIER_PIN=(5426689,"5eef22e497e9e0a867470c6c490336dc80fadd0e506e3419847e6c37b687918b")
GROWTH_CORE_SESSIONS=("lhqcore-20261003a","lhqcore-20261005a","lhqcore-20261005b","lhqcore-20261005c")
def _growth_carrier_anchor(raw):
 import ast
 require((len(raw),digest(raw))==GROWTH_CARRIER_PIN,"GROWTH_CARRIER_PIN")
 tree=ast.parse(raw)
 assignments,accepted=[],set()
 for node in tree.body:
  targets=node.targets if isinstance(node,ast.Assign) else [node.target] if isinstance(node,ast.AnnAssign) else []
  for target in targets:
   if isinstance(target,ast.Name) and target.id=="WRAPPER":
    require(isinstance(node.value,ast.Constant) and type(node.value.value) is str,
"GROWTH_WRAPPER_LITERAL")
    assignments.append(node.value.value)
    accepted.add(id(target))
 require(len(assignments)==1 and all(id(node) in accepted for node in ast.walk(tree)
if isinstance(node,ast.Name) and node.id=="WRAPPER" and isinstance(node.ctx,(ast.Store,ast.Del))),
"GROWTH_WRAPPER_LITERAL")
 path=assignments[0]
 prior.r.path_value(path)
 require(Path(path).name=="ssh.sh","GROWTH_WRAPPER_PATH")
 anchor=str(Path(path).parent)
 prior.r.path_value(anchor)
 return anchor
def _growth_frame_anchor(raw):
 import io
 import zipfile
 from e3_host import q2_local_source_delivery as source
 require((len(raw),digest(raw))==GROWTH_FRAME_PIN,"GROWTH_FRAME_PIN")
 lines=raw.splitlines(keepends=True)
 require(len(lines)>=3 and lines[0].startswith(source.HEADER) and lines[-1]==source.END,
"GROWTH_FRAME_FORMAT")
 encoded=bytearray()
 for line in lines[1:-1]:
  require(line.startswith(b"#") and line.endswith(b"\n") and 1<len(line)<=source.LINE_LIMIT,
"GROWTH_FRAME_LINE")
  encoded.extend(line[1:-1])
 package=base64.b64decode(encoded,validate=True)
 require(len(package)<=source.PACKAGE_LIMIT and source.frame_bytes(package)==raw,
"GROWTH_FRAME_CANONICAL")
 with zipfile.ZipFile(io.BytesIO(package)) as archive:
  entries=archive.infolist()
  require(0<len(entries)<=128 and len({row.filename for row in entries})==len(entries)
and sum(row.file_size for row in entries)<=source.EXPANDED_LIMIT,"GROWTH_FRAME_MEMBERS")
  row=archive.getinfo("sources/P")
  require(not row.is_dir() and not row.flag_bits & 1 and row.file_size==GROWTH_CARRIER_PIN[0],
"GROWTH_CARRIER_MEMBER")
  with archive.open(row) as stream:
   carrier=stream.read(GROWTH_CARRIER_PIN[0]+1)
 return _growth_carrier_anchor(carrier)
def _growth_plan_members(raw):
 import io
 import tarfile
 from e3_host import q2_core_approved_inputs as approved
 require((len(raw),digest(raw))==prior.PLAN_ARCHIVE,"GROWTH_PLAN_ARCHIVE_PIN")
 pins={path:(role,size,sha) for role,path,size,sha in approved.LOCATOR_MEMBERS}
 selected,seen,total={},set(),0
 with tarfile.open(fileobj=io.BytesIO(raw),mode="r|gz") as archive:
  for member in archive:
   require(member.name not in seen and len(seen)<20000,"GROWTH_PLAN_MEMBERS")
   seen.add(member.name)
   total+=member.size
   require(0<=member.size and total<=536870912,"GROWTH_PLAN_EXPANSION")
   if member.name not in pins:
    continue
   role,size,sha=pins[member.name]
   require(member.isfile() and not member.islnk() and not member.issym() and member.size==size,
"GROWTH_PLAN_MEMBER")
   with archive.extractfile(member) as stream:
    content=stream.read(size+1)
   require((len(content),digest(content))==(size,sha),"GROWTH_PLAN_MEMBER_PIN")
   selected[role]=prior.r.parse(content,size)
 require(set(selected)=={row[0] for row in approved.LOCATOR_MEMBERS},"GROWTH_PLAN_MEMBER_SET")
 return selected
def _growth_inventory(original,retry,documents,horizon,paths):
 protected,essential,groups,domain_rows,units,boots=set(),set(),set(),{},{},set()
 def path(value):
  prior.r.path_value(value)
  return value
 def protect(value,required=False):
  value=path(value)
  protected.add(value)
  if required:
   essential.add(value)
 def unit(value):
  require(type(value) is str and re.fullmatch(r"[A-Za-z0-9@_.:-]{1,180}\.service",value),
"GROWTH_INPUT_UNIT")
  if not re.fullmatch(r"user@[0-9]+\.service",value):
   units[value]={"name":value,"control_group":None}
 def scan_units(value,depth=0,counter=None):
  counter=[0] if counter is None else counter
  counter[0]+=1
  require(depth<=32 and counter[0]<=65536,"GROWTH_INPUT_COMPLEXITY")
  if type(value) is dict:
   for key,child in value.items():
    if key in ("unit","Id") and type(child) is str and child.endswith(".service"):
     unit(child)
    scan_units(child,depth+1,counter)
  elif type(value) is list:
   for child in value:
    scan_units(child,depth+1,counter)
 def observed_parents(value):
  if type(value) is not dict:
   return
  for role,row in value.items():
   if role=="manager" or type(row) is not dict or "path" not in row or "unit" not in row:
    continue
   name,control=row["unit"],path(row["path"])
   require(type(name) is str and re.fullmatch(r"[A-Za-z0-9_.-]{1,180}\.slice",name),
"GROWTH_INPUT_DOMAIN")
   groups.add(control)
   manager="user" if control.startswith("/user.slice/") else "system"
   domain_rows[manager,name,control]=dict(name=name,manager=manager,control_group=control)
 plans=[original,*[document for (batch,role),document in documents.items() if role=="plan"]]
 for plan in plans:
  require(type(plan) is dict and type(plan.get("host")) is dict,"GROWTH_INPUT_PLAN")
  boot=plan["host"].get("boot_id")
  require(type(boot) is str and re.fullmatch(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}",boot),
"GROWTH_INPUT_BOOT")
  boots.add(boot)
  for key in ("retained","retained_inputs"):
   for row in plan.get(key,[]):
    protect(row["path"],True)
  for row in plan.get("directories",{}).values():
   protect(row["path"])
  candidate=plan.get("candidate",{})
  for key in ("destination","source"):
   if key in candidate:
    protect(candidate[key])
  if "receipt_path" in candidate:
   protect(candidate["receipt_path"],True)
  for role,row in plan.get("parents",{}).items():
   if role=="ordinary":
    name=row["unit"]
    controller=plan["parents"].get("controller",{}).get("unit","")
    if controller.endswith(".slice") and name.startswith(controller.removesuffix(".slice")+"-"):
     observed_parents({role:dict(unit=name,path="/"+controller+"/"+name)})
    continue
   name=row["unit"]
   observed_parents({role:dict(unit=name,path="/"+name)})
  retained_parent=plan.get("retained_ordinary_parent")
  if type(retained_parent) is dict and "path" in retained_parent:
   observed_parents({"ordinary":dict(unit=Path(retained_parent["path"]).name,
path=retained_parent["path"])})
  scan_units(plan)
 require(len(boots)==1,"GROWTH_INPUT_BOOT_DRIFT")
 observed_parents(retry.get("facts",{}).get("parents"))
 scan_units(retry)
 for value in documents.values():
  observed_parents(value.get("parents"))
  scan_units(value)
 require(len(horizon["effective_rows"])==36,"GROWTH_INPUT_HORIZON")
 for row in horizon["effective_rows"]:
  for value in row["covered_paths"]:
   protect(value)
  for value in row["evidence"]:
   protect(value,True)
 for session in GROWTH_CORE_SESSIONS:
  unit(session.replace("-","",1)+"-carrier.service")
  for role in ("state","quota","journal","evidence"):
   protect(paths[role]+"/"+session)
  date=session.removeprefix("lhqcore-")
  for name in ("local-hand-core-acceptance-"+date,".local-hand-core-acceptance-"+date+".staging"):
   protect(paths["install"]+"/"+name)
 require(groups and any(row["manager"]=="user" for row in domain_rows.values()),
"GROWTH_INPUT_ORDINARY_DOMAIN")
 require(0<len(protected)<=1024 and 0<len(essential)<=512 and 0<len(units)<=128
and len(groups)<=32 and len(domain_rows)<=32,"GROWTH_INPUT_INVENTORY_LIMIT")
 inventory=dict(expected_units=[units[name] for name in sorted(units)],domain_cgroups=sorted(groups),
domain_units=[domain_rows[key] for key in sorted(domain_rows)],
protected_roots=sorted(protected),essential_paths=sorted(essential))
 require(len(canonical(inventory))<=131072,"GROWTH_INPUT_INVENTORY_BYTES")
 return inventory,boots.pop()
Q1_REPORT_PIN=(9632,"0183b985fdab6a755e96c916617484e274f38e284e575dcb298349d44ccba1e9")
Q1_EXPORT_PIN=(20208,"a5265e00222eb9cea4a9675627650c4a51adeac69c6383732a3aac0e3a3b8deb")
Q1_ROLES=("report","prepared","started","capture","stdout","stderr","old_marker","old_stderr")
def q1_declaration(raw):
 """Derive the one approved forward declaration from retained originals only."""
 from e3_host import q2_host_export as e,q2_journal_growth_guest as g
 import json
 require(type(raw) is dict and set(raw)==set(Q1_ROLES),"GROWTH_Q1_ROLES")
 for role,data in raw.items():
  require(type(data) is bytes and len(data)<=(MIB if role in ("stdout","stderr") else 65536),"GROWTH_Q1_LIMIT")
 require((len(raw["report"]),digest(raw["report"]))==Q1_REPORT_PIN,"GROWTH_Q1_REPORT_PIN")
 for role,name in (("old_marker","consumed.json"),("old_stderr","pre.stderr")):
  require((len(raw[role]),digest(raw[role]))==history.SEVENTH_JOURNAL_PINS[name],"GROWTH_Q1_OLD_PIN")
 report=e.document(raw["report"])
 require((report.get("schema"),report.get("scope"),report.get("status"),report.get("source_config_status"))==
 ("local-hand-q2-host-export/v1","READ_ONLY_SELECTED_Q1_HOST_HANDOFF","EXPORTED","Q1_EVIDENCE_ONLY"),"GROWTH_Q1_REPORT")
 require(all(report.get(k) is False for k in ("q1_history_reassessed","q2_accepted","q3_accepted",
 "production_supported","complete_q1_domain_inventory","quota_observed","current_capacity_is_new_budget","fixture_generated"))
 and report.get("independent_supervision_required") is True
 and report.get("q2_input_groups")==dict.fromkeys(e.MISSING,"NOT_DELIVERED"),"GROWTH_Q1_COVERAGE")
 def row(name):
  rows=[x for x in report["checks"] if type(x) is dict and x.get("check")==name]
  require(len(rows)==1 and rows[0].get("status")=="OBSERVED","GROWTH_Q1_ROW")
  return rows[0]["facts"]
 prepared,started,marker,old=[prior.r.parse(raw[k],65536) for k in
 ("prepared","started","old_marker","old_stderr")]
 # The retained native capture has one finite elapsed-seconds decimal. Keep
 # its original bytes pinned; all authority/identity/clock numbers stay ints.
 from decimal import Decimal
 def pairs(items):
  value={}
  for key,item in items:
   require(key not in value,"GROWTH_Q1_CAPTURE_DUPLICATE");value[key]=item
  return value
 capture=json.loads(raw["capture"],object_pairs_hook=pairs,parse_float=Decimal,parse_constant=Decimal)
 elapsed=capture.pop("elapsed_seconds",None)
 require(type(elapsed) in (int,Decimal) and 0<=elapsed<=60,"GROWTH_Q1_CAPTURE_ELAPSED")
 # json.dumps rejects every other Decimal (including NaN/Infinity).
 capture=prior.r.parse(json.dumps(capture,allow_nan=False).encode("ascii"),65536)
 require(prepared.get("kind")==capture.get("kind")=="CURRENT_OBSERVATION"
 and prepared.get("task_commit")=="38ff001" and prepared.get("manager")=="system"
 and type(prepared.get("field_commands")) is int and prepared["field_commands"]==1
 and prepared.get("retry") is False and prepared.get("prior_D")==history.SEVENTH_JOURNAL_D,
 "GROWTH_Q1_CAPTURE_ORIGIN")
 require(started.get("prepared_sha256")==digest(raw["prepared"]) and capture.get("start")==started
 and capture.get("complete") is True and capture.get("error") is None
 and type(capture.get("exit_code")) is int and capture["exit_code"]==0
 and type(capture.get("ssh_requests_attempted")) is int and capture["ssh_requests_attempted"]==1
 and capture.get("eof")==dict(stdout=True,stderr=True) and raw["stderr"]==b"",
 "GROWTH_Q1_CAPTURE_INDEX")
 require(capture.get("streams")=={k:dict(bytes=len(raw[k]),sha256=digest(raw[k]),truncated=False) for k in ("stdout","stderr")},
 "GROWTH_Q1_STREAM_PIN")
 require(prepared.get("source_originals")=={name:dict(bytes=len(raw[role]),sha256=digest(raw[role]))
 for role,name in (("old_marker","consumed.json"),("old_stderr","pre.stderr"))}
 and prepared.get("description")==marker["pre_description"]
 and prepared.get("prior_manifest_sha256")==marker["manifest_sha256"],"GROWTH_Q1_OLD_SOURCE")
 unit=prepared["unit"]
 require(old.get("diagnostic",{}).get("context",{}).get("unit")==unit,"GROWTH_Q1_REQUEST")
 # No remote executor or GuestInventory constructor is involved.
 inv=object.__new__(g.GuestInventory);inv.context={}
 def retained_ctl(args,*,user_uid=None):
  require(user_uid is None and args==["show","--all","--property="+",".join(g.GuestInventory.SHOW),"--",unit],
 "GROWTH_Q1_QUERY_SHAPE")
  return raw["stdout"]
 inv.ctl=retained_ctl
 properties=inv.show_many([unit])[unit]
 require(properties["Id"]==unit and properties["LoadState"]=="loaded","GROWTH_Q1_ID")
 command=properties.get("ExecStart","")
 match=re.fullmatch(r"\{ path=(/[A-Za-z0-9_./-]+) ; argv\[\]=([^;\n]+) ; ignore_errors=no ;[^\n]* \}",command)
 require(match is not None and command.count("argv[]=")==1,"GROWTH_Q1_COMMAND")
 argv=match[2].split(" ")
 require(len(argv)==7 and argv[1:3]==["-I","-B"] and argv[0]==match[1],"GROWTH_Q1_ARGUMENTS")
 configs={label:row(label+"_config") for label in ("original","revision")}
 for value in configs.values():
  require(value.get("status")=="Q1_CONFIG_BYTES_LINKED_ONLY"
 and value.get("independent_authority_proven") is value.get("q2_reusable_allocation") is False,"GROWTH_Q1_CONFIG")
  for key in ("runtime.json","manifest.json"):e.token(value["files"][key],e.HEX)
 require([label for label,value in configs.items() if value["files"]["runtime.json"]==argv[5]]==["original"],
 "GROWTH_Q1_RUNTIME_PAIR")
 config=configs["original"];manifest=config["files"]["manifest.json"]
 require(argv[0]==row("original_program_python")["path"] and argv[3]==row("original_program_worker")["path"],
 "GROWTH_Q1_PROGRAM")
 suffix="/source/tools/admin/local_hand_quota_observer/worker.py"
 require(argv[3].endswith(suffix),"GROWTH_Q1_WORKER")
 base=argv[3][:-len(suffix)]
 require(argv[4]==base+"/config/runtime.json" and base in prepared["description"]["protected_roots"],"GROWTH_Q1_PATH")
 e.path(argv[3]);e.path(argv[4]);e.token(argv[6],r"[A-Za-z0-9+/]{1,10922}={0,2}")
 ticket_raw=base64.b64decode(argv[6],validate=True)
 require(base64.b64encode(ticket_raw).decode("ascii")==argv[6],"GROWTH_Q1_BASE64")
 ticket=e.document(ticket_raw)
 e.keys(ticket,("schema","slot_ref","generation","request_id","allocation_digest","execution_id","phase","issued_ns","deadline_ns"))
 require(ticket["schema"]=="local-hand-quota-ticket/v1" and json.dumps(ticket,sort_keys=True,separators=(",",":")).encode()==ticket_raw,
 "GROWTH_Q1_TICKET")
 for key,pattern in (("slot_ref",r"[a-z0-9][a-z0-9_.-]{0,63}"),("generation",r"[0-9a-f]{32}"),
 ("request_id",r"[0-9a-f]{32}"),("allocation_digest",e.HEX),("execution_id",r"[0-9a-f]{32}")):
  e.token(ticket[key],pattern)
 require(type(ticket["phase"]) is str and ticket["phase"] in ("preflight","business","reconcile","evidence"),"GROWTH_Q1_PHASE")
 e.number(ticket["issued_ns"]);e.number(ticket["deadline_ns"],ticket["issued_ns"]+1)
 identity=[manifest]+[ticket[k] for k in ("slot_ref","generation","request_id","allocation_digest","execution_id","phase")]
 require("lhq-"+digest(json.dumps(identity,separators=(",",":")).encode())+".service"==unit,"GROWTH_Q1_IDENTITY")
 head=row("original_source_head");row("original_current_boot")
 e.token(config["source_commit"],e.COMMIT);e.token(config["boot_id"],e.UUID)
 require(config["source_commit"]==head["declared_commit"]==head["detached_head"]
 and head["source_bytes_verified"] is head["clean_tree_verified"] is False
 and config["boot_id"]==row("declared_guest")["boot_id"]==prepared["description"]["original_boot_id"],"GROWTH_Q1_SOURCE")
 parent=row("original_query_parent")
 require(parent.get("q2_parent_admitted") is False and type(parent.get("path")) is str
 and re.fullmatch(r"/sys/fs/cgroup/lhq[a-z0-9]{1,40}\.slice",parent["path"]),"GROWTH_Q1_PARENT")
 logical=parent["path"].removeprefix("/sys/fs/cgroup")
 keys=("expected_units","domain_units","domain_cgroups","protected_roots","essential_paths")
 original={k:prepared["description"][k] for k in keys}
 additions=dict(expected_units=[dict(name=unit,control_group=logical+"/"+unit)],
 domain_units=[dict(name=logical[1:],manager="system",control_group=logical)],domain_cgroups=[logical])
 proof=dict(schema="lhq-journal-q1-declaration/v1",scope=history.c.QI_SCOPE,
 sources={k:dict(bytes=len(v),sha256=digest(v)) for k,v in raw.items()},config="original_config",
 runtime_sha256=argv[5],manifest_sha256=manifest,ticket_sha256=digest(ticket_raw),
 boot_id=config["boot_id"],source_commit=config["source_commit"],additions=additions,additions_sha256=digest(canonical(additions)),
 original_inventory_sha256=digest(canonical(original)),independent_authority_proven=False,
 q2_reusable_allocation=False,q2_parent_admitted=False,full_manifest_validated=False)
 return original,proof
def merge_q1_inventory(original,proof):
 import copy
 require([len(original[k]) for k in ("expected_units","domain_units","domain_cgroups")]==[18,6,6],"GROWTH_Q1_BASE_COUNT")
 additions=proof["additions"];service=additions["expected_units"][0];domain=additions["domain_units"][0]
 require(all(x["name"] not in (service["name"],domain["name"])
 and x["control_group"] not in (service["control_group"],domain["control_group"])
 for x in original["expected_units"]+original["domain_units"])
 and domain["control_group"] not in original["domain_cgroups"],"GROWTH_Q1_CONFLICT")
 value=copy.deepcopy(original)
 for key,rows in additions.items():value[key].extend(copy.deepcopy(rows))
 value["expected_units"].sort(key=lambda x:x["name"])
 value["domain_units"].sort(key=lambda x:(x["manager"],x["name"],x["control_group"]))
 value["domain_cgroups"].sort()
 require(len(canonical(value))<=131072,"GROWTH_INPUT_INVENTORY_BYTES")
 return value
def read_q1_inputs(inputs,spec):
 require(type(spec) is dict and set(spec)==set(Q1_ROLES),"GROWTH_Q1_SOURCES_REQUIRED")
 raw={}
 for role in Q1_ROLES:
  row=spec[role]
  require(type(row) is dict and set(row)=={"path","bytes","sha256"},"GROWTH_Q1_PIN_FIELDS")
  prior.r.path_value(row["path"]);prior.r.integer(row["bytes"],0,MIB if role in ("stdout","stderr") else 65536)
  require(type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}",row["sha256"]),"GROWTH_Q1_PIN")
  raw[role]=inputs.read(row["path"],row["bytes"],row["sha256"],"q1_"+role)
 require(len({(os.fstat(fd).st_dev,os.fstat(fd).st_ino) for _,fd,_ in inputs.held})==len(inputs.held),"GROWTH_Q1_SOURCE_ALIAS")
 return raw
def recheck_q1_inputs(inputs,frozen,check=lambda:None):
 for role,row in frozen["q1_sources"].items():
  fd=next(fd for path,fd,_ in inputs.held if path==row["path"])
  check();os.lseek(fd,0,os.SEEK_SET)
  raw,_=local.stable_read(fd,row["bytes"],check)
  require(raw==frozen["q1_raw"][role] and digest(raw)==row["sha256"],"GROWTH_Q1_SOURCE_DRIFT")
 inputs.recheck(check)
def validate_q1_frozen(frozen):
 original,proof=q1_declaration(frozen["q1_raw"])
 activation=frozen.get("vm_activation")
 if activation is not None:
  require(history.build_vm_activation(frozen["activation_files"],frozen["activation_index"],
 historical_boot=proof["boot_id"])==activation==frozen["source_binding"]["vm_activation"]
 and frozen["boot_id"]==activation["current_boot_id"],"GROWTH_ACTIVATION_FROZEN")
 require(proof==frozen["source_binding"]["q1_declaration"]
 and proof["boot_id"]==(activation["historical_boot_id"] if activation else frozen["boot_id"])
 and merge_q1_inventory(original,proof)==frozen["inventory"],"GROWTH_Q1_FROZEN_BINDING")
 for role,pin in proof["sources"].items():
  require(frozen["source_binding"]["sources"]["q1_"+role]==pin,"GROWTH_Q1_FROZEN_PIN")
 return proof
def runtime_parent_binding(original,retry,system):
 try:return history.runtime_parent_binding(original,retry,system)
 except history.c.ContractError as error:raise prior.r.ObservationError(str(error)) from error
def freeze_growth_inputs(inputs,frame_path,plan_archive,archives_dir,*,q1_sources=None):
 raw=inputs.read(frame_path,*GROWTH_FRAME_PIN,"management_frame")
 anchor_path=_growth_frame_anchor(raw)
 archive=inputs.read(plan_archive,*prior.PLAN_ARCHIVE,"plan_archive")
 selected=_growth_plan_members(archive)
 description=prior.plan_from_archive(archive)
 paths=prior.r.description(description)["paths"]
 archives={batch:inputs.read(Path(archives_dir) / name,size,sha,batch)
for batch,name,size,sha in prior.obligations.ARCHIVES}
 documents=prior.obligations.read_horizon(archives)
 horizon=prior.obligations.build_horizon(archives)
 prior.verify_threshold_anchors(horizon)
 inventory,boot=_growth_inventory(selected["original_plan"],selected["retry_preparation"],
documents,horizon,paths)
 q1_raw=read_q1_inputs(inputs,q1_sources)
 original,proof=q1_declaration(q1_raw)
 # The four carrier cgroups are separately recovered from their original HELLOs.
 import copy
 before=copy.deepcopy(original)
 carriers={session.replace("-","",1)+"-carrier.service" for session in GROWTH_CORE_SESSIONS}
 for row in before["expected_units"]:
  if row["name"] in carriers:row["control_group"]=None
 require(before==inventory and proof["boot_id"]==boot,"GROWTH_Q1_ORIGINAL_INVENTORY")
 inventory=merge_q1_inventory(inventory,proof)
 runtime=runtime_parent_binding(selected["original_plan"],selected["retry_preparation"],documents["20261001e","plan"])
 from e3_host import q2_journal_growth_guest as g
 g.validate_runtime_binding(runtime,inventory)
 binding=dict(sources=dict(inputs.bindings),plan_sha256=prior.r.PLAN_SHA,
runtime_parent_binding_sha256=digest(canonical(runtime)),
inventory_sha256=digest(canonical(inventory)),
description_sha256=digest(description),horizon_sha256=digest(canonical(horizon)),q1_declaration=proof)
 inputs.recheck()
 return dict(anchor_path=anchor_path,paths=paths,description=description,horizon=horizon,boot_id=boot,
inventory=inventory,runtime_parent_binding=runtime,source_binding=binding,source_binding_sha256=digest(canonical(binding)),q1_raw=q1_raw,q1_sources=q1_sources)

def adopt_vm_activation(inputs,frozen,spec):
 """One fixed retained archive keeps the original descriptor/FD limits."""
 require(type(spec) is dict and set(spec)=={"path","bytes","sha256"},"GROWTH_ACTIVATION_SPEC")
 prior.r.path_value(spec["path"]);prior.r.integer(spec["bytes"],1,524288)
 raw=inputs.read(spec["path"],spec["bytes"],spec["sha256"],"vm_activation_archive")
 try:files=history.activation_archive_files(raw)
 except history.c.ContractError as error:raise prior.r.ObservationError("GROWTH_ACTIVATION_ARCHIVE") from error
 index=files.pop("execution-return-index-private.json")
 activation=history.build_vm_activation(files,index,historical_boot=frozen["boot_id"])
 frozen.update(vm_activation=activation,activation_files=files,activation_index=index,activation_archive=spec)
 frozen["source_binding"]["vm_activation"]=activation
 frozen["source_binding"]["sources"]["vm_activation_archive"]=dict(bytes=len(raw),sha256=digest(raw))
 frozen["boot_id"]=activation["current_boot_id"]
 frozen["source_binding_sha256"]=digest(canonical(frozen["source_binding"]))
 validate_q1_frozen(frozen)
 return activation

def recheck_vm_activation(inputs,frozen,check):
 if frozen.get("vm_activation") is None:return
 spec=frozen["activation_archive"]
 fd=next(fd for path,fd,_ in inputs.held if path==spec["path"])
 check();os.lseek(fd,0,os.SEEK_SET)
 raw,_=local.stable_read(fd,spec["bytes"],check)
 require(digest(raw)==spec["sha256"],"GROWTH_ACTIVATION_SOURCE_DRIFT")
 inputs.recheck(check)

class ImageSet:
 def __init__(self,anchor_fd,anchor,argv,check,*,activation=None):
  self.anchor_fd,self.anchor,self.check=anchor_fd,anchor,check
  self.parent_identity=identity(os.fstat(anchor_fd))
  self.fds,self.paths,self.initial={},{},{}
  self.external_parent=None
  self.activation=activation
  self.owner=os.geteuid()
  try:
   drives=[argv[index+1] for index,word in enumerate(argv[:-1]) if word=="-drive"]
   require(len(drives)==5,"GROWTH_DRIVE_COUNT")
   for drive in drives:
    fields=drive.split(",")
    require(all("=" in field for field in fields),"GROWTH_DRIVE_FORMAT")
    pairs=[field.split("=",1) for field in fields]
    options=dict(pairs)
    require(len(pairs)==len(options),"GROWTH_DRIVE_FORMAT")
    path=options.get("file","")
    external=activation is not None and path==activation["system_path"]
    require(re.fullmatch(r"/[A-Za-z0-9_./-]+",path)
and os.path.normpath(path)==path and (str(Path(path).parent)==anchor or external),
"GROWTH_IMAGE_PATH")
    name=Path(path).name
    if options.get("format")=="qcow2":
     require(name.endswith(".qcow2") and options.get("readonly","off")=="off",
"GROWTH_IMAGE_FORMAT")
     role=name[:-6] if name in ("quota.qcow2","journal.qcow2","evidence.qcow2") else "system"
     cap=IMAGE_CAP if role=="journal" else 32*1024**3
     if role=="journal":
      self.journal_drive_id=options.get("id","")
      require(re.fullmatch(r"[A-Za-z0-9_-]{1,64}",self.journal_drive_id),
"GROWTH_JOURNAL_DRIVE_ID")
    else:
     require(options.get("format")=="raw" and
(options.get("readonly")=="on" or options.get("media")=="cdrom"),
"GROWTH_SEED_FORMAT")
     role,cap="seed",16*MIB
    require(role not in self.fds,"GROWTH_DRIVE_ROLE")
    if external:
     require(role=="system" and options.get("id")=="os" and self.external_parent is None,"GROWTH_ACTIVATION_IMAGE_ROLE")
     self.external_parent=local.open_directory(str(Path(path).parent),self.owner)
     self.external_identity=identity(os.fstat(self.external_parent))
     cap=5*1024**3
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME|os.O_CLOEXEC,
dir_fd=self.external_parent if external else anchor_fd)
    self.fds[role],self.paths[role]=fd,path
    info=os.fstat(fd)
    validate_file(info,cap,self.owner)
    require(info.st_size>0,"GROWTH_EMPTY_IMAGE")
    self.initial[role]=info
   require(set(self.fds)=={"system","quota","journal","evidence","seed"},
"GROWTH_DRIVE_ROLE")
   devices=[]
   for index,word in enumerate(argv[:-1]):
    if word!="-device":
     continue
    parts=argv[index+1].split(",")
    pairs=[part.split("=",1) for part in parts[1:]]
    require(all(len(pair)==2 for pair in pairs),"GROWTH_DEVICE_FORMAT")
    options=dict(pairs)
    require(len(options)==len(pairs),"GROWTH_DEVICE_FORMAT")
    if options.get("drive")==self.journal_drive_id:
     require(parts[0]=="virtio-blk-pci","GROWTH_JOURNAL_DEVICE")
     devices.append(options.get("serial",""))
   require(len(devices)==1 and re.fullmatch(r"[A-Za-z0-9_.-]{1,20}",devices[0]),
"GROWTH_JOURNAL_SERIAL")
   self.journal_serial=devices[0]
   require(len(set(self.image_keys().values()))==5,"GROWTH_IMAGE_ALIAS")
   if activation is not None:
    history.validate_vm_activation(activation)
    require({role:list(value) for role,value in self.image_keys().items()}==activation["image_identities"],
 "GROWTH_ACTIVATION_IMAGE_BINDING")
   self.recheck()
  except BaseException:
   self.close()
   raise
 @property
 def journal_fd(self):
  return self.fds["journal"]
 @property
 def journal_path(self):
  return self.paths["journal"]
 def image_keys(self):
  return {role:(os.fstat(fd).st_dev,os.fstat(fd).st_ino) for role,fd in self.fds.items()}
 def recheck(self,*,stable=False,journal_changed=False):
  self.check()
  parent=local.open_directory(self.anchor,self.owner)
  try:
   require(identity(os.fstat(parent))==self.parent_identity==identity(os.fstat(self.anchor_fd)),
"GROWTH_IMAGE_PARENT_DRIFT")
   for role,fd in self.fds.items():
    info=os.fstat(fd)
    external=role=="system" and self.external_parent is not None
    if external:
     check_parent=local.open_directory(str(Path(self.paths[role]).parent),self.owner)
     try:require(identity(os.fstat(check_parent))==self.external_identity==identity(os.fstat(self.external_parent)),"GROWTH_ACTIVATION_PARENT_DRIFT")
     finally:os.close(check_parent)
    named=os.stat(Path(self.paths[role]).name,dir_fd=self.external_parent if external else parent,follow_symlinks=False)
    require(identity(info)==identity(named)==identity(self.initial[role]),"GROWTH_IMAGE_DRIFT")
    validate_file(info,5*1024**3 if external else IMAGE_CAP if role=="journal" else
(16*MIB if role=="seed" else 32*1024**3),self.owner)
    require(stable_identity(info)==stable_identity(named),"GROWTH_IMAGE_DRIFT")
    if role=="seed" or (stable and not (journal_changed and role=="journal")):
     require(stable_identity(info)==stable_identity(self.initial[role]),"GROWTH_IMAGE_WRITE")
  finally:
   os.close(parent)
 def checkpoint(self):
  self.recheck()
  self.initial={role:os.fstat(fd) for role,fd in self.fds.items()}
 def capacity(self):
  self.recheck()
  for fd in self.fds.values():
   value=os.fstatvfs(fd)
   require(value.f_bavail*value.f_frsize>=HOST_BYTES and value.f_favail>=HOST_INODES,
"GROWTH_HOST_CAPACITY")
 def offline_info(self,tool,expected_size):
  self.recheck(stable=True)
  commands=image_commands(self.journal_path,self.journal_path)
  output=tool.run(commands["info"])
  value=validate_image_info(output["stdout"],expected_size)
  checked=tool.run(commands["check"])
  result=prior.r.parse(checked["stdout"],65536)
  require(result.get("check-errors",0)==0 and result.get("corruptions",0)==0
and result.get("leaks",0)==0,"GROWTH_IMAGE_CHECK")
  self.recheck(stable=True)
  return dict(info=value,check=result,check_returncode=checked["returncode"],check_eof=checked["eof"])
 def grow(self,tool,backup_path):
  self.recheck(stable=True)
  require(backup_path==self.anchor+"/"+NAMES["journal.backup.qcow2"],"GROWTH_BACKUP_PATH")
  commands=image_commands(self.journal_path,backup_path)
  tool.run(commands["resize"])
  self.recheck(stable=True,journal_changed=True)
  self.checkpoint()
  result=self.offline_info(tool,NEW_SIZE)
  compared=tool.run(commands["compare"])
  result["logical_compare"]=dict(returncode=compared["returncode"],eof=compared["eof"])
  self.recheck(stable=True)
  return result
 def close(self):
  for fd in self.fds.values():
   os.close(fd)
  self.fds.clear()
  if self.external_parent is not None:os.close(self.external_parent);self.external_parent=None
def pidfile(anchor_fd,suffix,check):
 require(suffix in ("vm.pid",NAMES["vm.pid"]),"GROWTH_PIDFILE_NAME")
 check()
 fd=os.open(suffix,os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME|os.O_CLOEXEC,
dir_fd=anchor_fd)
 try:
  info=os.fstat(fd)
  validate_file(info,4096,os.geteuid())
  require(info.st_size<=64,"GROWTH_PIDFILE")
  raw=os.read(fd,65)
  require(re.fullmatch(rb"[1-9][0-9]{0,9}\n?",raw) and int(raw)>1,"GROWTH_PIDFILE")
  require(stable_identity(os.fstat(fd))==stable_identity(info)==
stable_identity(os.stat(suffix,dir_fd=anchor_fd,follow_symlinks=False)),"GROWTH_PIDFILE_DRIFT")
  check()
  return int(raw)
 finally:
  os.close(fd)
def freeze_vm(start,anchor,anchor_fd,qemu_tool,check,*,activation=None):
 if activation is None:pid=pidfile(anchor_fd,"vm.pid",check)
 else:
  history.validate_vm_activation(activation)
  require(Path(activation["pidfile"]).name=="vm.pid","GROWTH_ACTIVATION_PIDFILE")
  parent=local.open_directory(str(Path(activation["pidfile"]).parent),os.geteuid())
  try:pid=pidfile(parent,"vm.pid",check)
  finally:os.close(parent)
  require(pid==activation["vm"]["pid"],"GROWTH_ACTIVATION_PID")
 raw=proc_bytes(pid,"cmdline",65536,check)
 require(raw.endswith(b"\0"),"GROWTH_PROCESS_ARGV")
 current=[word.decode("ascii","strict") for word in raw[:-1].split(b"\0")]
 require(current.count("-serial")==1,"GROWTH_PROCESS_SERIAL")
 index=current.index("-serial")+1
 require(index<len(current) and current[index].startswith("file:"),"GROWTH_PROCESS_SERIAL")
 serial=current[index][5:]
 require(re.fullmatch(r"/[A-Za-z0-9_./-]{1,4095}",serial) and os.path.normpath(serial)==serial,
"GROWTH_PROCESS_SERIAL")
 original,restart=qemu_argv(start,anchor,serial,activation=activation)
 require(current==original,"GROWTH_PROCESS_ARGV")
 process=ProcessIdentity(pid,original,qemu_tool.fd,check)
 images=None
 try:
  images=ImageSet(anchor_fd,anchor,original,check,activation=activation)
  binding=process.recheck()
  require(activation is None or binding==activation["vm"],"GROWTH_ACTIVATION_PROCESS")
  return dict(process=process,images=images,original_argv=original,restart_argv=restart,
binding=binding)
 except BaseException:
  process.close()
  if images is not None:
   images.close()
  raise
GUEST_LOADER="""import base64,hashlib,json,sys,types,zlib
b=base64.b64decode(sys.argv[1],validate=True)
if len(b)>49152 or hashlib.sha256(b).hexdigest()!=sys.argv[2]: raise ValueError('BUNDLE_PIN')
z=zlib.decompressobj(); r=z.decompress(b,393217)
if len(r)>393216 or not z.eof or z.unconsumed_tail or z.unused_data: raise ValueError('BUNDLE_BOUND')
d=json.loads(r)
if type(d) is not dict or set(d)!={'encoding','reader','guest','input'} or d['encoding']!='utf8': raise ValueError('BUNDLE_ENCODING')
p=types.ModuleType('e3_host'); p.__path__=[]; sys.modules['e3_host']=p
for key,name in [('reader','q2_core_capacity_reader'),('guest','q2_journal_growth_guest')]:
 s=d[key].encode('utf-8')
 if not 0<len(s)<=(98304 if key=='guest' else 65536): raise ValueError('SOURCE_BOUND')
 m=types.ModuleType('e3_host.'+name); m.__package__='e3_host'; sys.modules[m.__name__]=m; setattr(p,name,m)
 exec(compile(s,'<'+name+'>','exec'),m.__dict__)
v=d['input'].encode('utf-8')
if len(v)>65536: raise ValueError('INPUT_BOUND')
sys.exit(m.entry(v))
"""
def source_bundle(sources,descriptor):
 import zlib
 value={"input":canonical(descriptor)}
 value.update({key:sources[name] for key,name in
(("reader","q2_core_capacity_reader.py"),("guest","q2_journal_growth_guest.py"))})
 require(all(type(raw) is bytes and 0<len(raw)<=(98304 if key=="guest" else 65536)
 for key,raw in value.items()),"GROWTH_BUNDLE_INPUT")
 # Preserve source bytes via strict UTF-8, avoiding base64 inside compressed JSON.
 raw=canonical(dict(encoding="utf8",**{key:data.decode("utf-8","strict") for key,data in value.items()}))
 require(len(raw)<=393216,"GROWTH_BUNDLE_BOUND")
 compressed=zlib.compress(raw,9)
 require(len(compressed)<=49152,"GROWTH_BUNDLE_BOUND")
 return base64.b64encode(compressed).decode("ascii"),digest(compressed)
def remote_argv(anchor_path,sources,descriptor):
 encoded,sha=source_bundle(sources,descriptor)
 command=["exec","/usr/bin/sudo","-n","--","/usr/bin/env","-i","HOME=/root",
"PATH=/usr/bin:/bin","LANG=C","LC_ALL=C","/usr/bin/python3","-I","-B","-c",
GUEST_LOADER,encoded,sha]
 argv=local.make_argv(anchor_path,b"# unused")[:-1]+[shlex.join(command)]
 require(sum(len(word.encode())+1 for word in argv)<=65536,"GROWTH_ARGV_LIMIT")
 return argv
class MaintenanceTransport:
 def __init__(self,anchor,store,argv,phase,nonce,source_binding_sha256,original_boot_id,
check,*,validate=None,popen=subprocess.Popen):
  require(phase in ("pre","post"),"GROWTH_PHASE")
  self.store,self.check,self.phase=store,check,phase
  self.nonce,self.source_sha,self.old_boot=nonce,source_binding_sha256,original_boot_id
  self.validate,self.report,self.sent,self.offset=validate,None,False,0
  self.is_vm=False
  self.output={name:bytearray() for name in ("stdout","stderr")}
  self.eof={name:False for name in self.output}
  self.fds={}
  self.selector,self.process=None,None
  stage="capture_stdout"
  try:
   for name in self.output:
    stage="capture_"+name
    self.fds[name]=store.create(phase+"."+name)
   stage="selector"
   self.selector=selectors.DefaultSelector()
   check()
   env={key:os.environ[key] for key in ("HOME","USER","LOGNAME") if key in os.environ}
   env.update(PATH="/usr/bin:/bin",LANG="C",LC_ALL="C")
   require(sum(len(x.encode())+1 for x in argv)+
sum(len((k+"="+v).encode())+1 for k,v in env.items())<=65536,"GROWTH_ARGV_LIMIT")
   stage="spawn"
   self.process=popen(argv,executable=f"/proc/self/fd/{anchor.ssh}",pass_fds=(anchor.ssh,),
stdin=subprocess.PIPE if phase=="pre" else subprocess.DEVNULL,
stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,
preexec_fn=control_limits,start_new_session=True)
   self.identity=dict(pid=self.process.pid,argv_sha256=digest(canonical(argv)),starttime=None)
   COMMANDS.append(self)
   stage="pipe_registration"
   for name in self.output:
    stream=getattr(self.process,name)
    os.set_blocking(stream.fileno(),False)
    self.selector.register(stream,selectors.EVENT_READ,name)
  except BaseException as error:
   error.growth_transport=self
   if not hasattr(error,"diagnostic"):
    error.diagnostic=dict(operation="maintenance_transport_construct",phase=phase,
stage=stage,process_created=self.process is not None)
   self.close()
   raise
 def pump(self):
  self.check()
  for key,_ in self.selector.select(0.05):
   name=key.data
   raw=os.read(key.fileobj.fileno(),min(65536,MIB+1-len(self.output[name])))
   self.check()
   if not raw:
    self.eof[name]=True
    self.selector.unregister(key.fileobj)
   else:
    room=MIB-len(self.output[name])
    part=raw[:room]
    write_all(self.fds[name],part,self.check)
    self.output[name].extend(part)
    require(len(raw)<=room,"GROWTH_STREAM_LIMIT")
    self.store.budget()
 def seal(self):
  for name,fd in self.fds.items():
   os.fsync(fd)
   require(hash_fd(fd,MIB,self.check)==dict(bytes=len(self.output[name]),
sha256=digest(bytes(self.output[name]))),"GROWTH_STREAM_REREAD")
   os.lseek(fd,0,os.SEEK_END)
  self.store.budget()
 def receive_report(self):
  require(self.report is None,"GROWTH_REPORT_ONCE")
  try:
   while b"\n" not in self.output["stdout"]:
    require(not self.eof["stdout"],"GROWTH_REPORT_MISSING")
    self.pump()
   raw=bytes(self.output["stdout"]).split(b"\n",1)[0]+b"\n"
   value=prior.r.parse(raw,MIB)
   require(canonical(value)==raw and value.get("schema")==REPORT_SCHEMA
and value.get("session")==SESSION and value.get("phase")==self.phase
and value.get("nonce")==self.nonce and value.get("source_binding_sha256")==self.source_sha
and value.get("status")==("GUEST_QUIET" if self.phase=="pre" else "FILESYSTEM_GROWN"),
"GROWTH_REPORT_BINDING")
   boot=value.get("boot_id")
   require(type(boot) is str and re.fullmatch(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}",boot)
and ((boot==self.old_boot) if self.phase=="pre" else
(boot!=self.old_boot and value.get("original_boot_id")==self.old_boot)),"GROWTH_REPORT_BOOT")
   if self.validate is not None:
    self.validate(value)
   self.seal()
   self.report,self.offset=value,len(raw)
   return value
  except BaseException as error:
   error.growth_transport=self
   raise
 def continue_poweroff(self,pre_digest):
  require(self.phase=="pre" and self.report is not None and not self.sent
and pre_digest==digest(canonical(self.report)),"GROWTH_CONTINUE_BINDING")
  self.sent=True  # A partial write also permanently spends the one token.
  try:
   self.seal()
   self.store.event(dict(step="POWER_OFF_TOKEN",state="STARTED",pre_report_sha256=pre_digest))
   self.check()
   token=continue_token(self.nonce,pre_digest)
   fd=self.process.stdin.fileno()
   os.set_blocking(fd,False)
   require(os.write(fd,token)==len(token),"GROWTH_TOKEN_SHORT_WRITE")
   self.process.stdin.close()
  except BaseException as error:
   error.growth_transport=self
   raise
 def finish(self):
  try:
   require(self.report is not None and (self.phase=="post" or self.sent),"GROWTH_FINISH_ORDER")
   while self.selector.get_map() or self.process.poll() is None:
    self.pump()
   self.seal()
   tail=bytes(self.output["stdout"])[self.offset:]
   ack=None
   if self.phase=="pre":
    ack=prior.r.parse(tail,MIB)
    validate_startup_assurance(ack.get("guest_startup_assurance"))
    require(tail==canonical(ack) and ack==dict(schema=REPORT_SCHEMA,
session=SESSION,status="POWER_OFF_REQUESTED",nonce=self.nonce,
pre_report_sha256=digest(canonical(self.report)),
guest_startup_assurance=guest_startup_assurance()),"GROWTH_POWER_OFF_ACK")
    require(self.process.returncode in (0,255),"GROWTH_PRE_RETURN")
   else:
    require(not tail and self.process.returncode==0,"GROWTH_POST_RETURN")
   return dict(returncode=self.process.returncode,eof=dict(self.eof),ack=ack,
files={name:dict(bytes=len(raw),sha256=digest(bytes(raw))) for name,raw in self.output.items()})
  except BaseException as error:
   error.growth_transport=self
   raise
  finally:
   self.close()
 def close(self):
  if self.selector is not None:
   self.selector.close()
  if self.process is not None:
   for name in ("stdin","stdout","stderr"):
    stream=getattr(self.process,name)
    if stream is not None and not stream.closed:
     stream.close()
def continue_token(nonce,pre_digest):
 require(re.fullmatch("[0-9a-f]{64}",nonce) and re.fullmatch("[0-9a-f]{64}",pre_digest),
"GROWTH_TOKEN_BINDING")
 return ("POWER_OFF "+SESSION+" "+nonce+" "+pre_digest+"\n").encode("ascii")
def field_readiness():
 return dict(state="BLOCKED",code="GROWTH_J2_NOT_FROZEN",marker_created=False,
ssh_requests=0,business_cases=0,
missing=["T2 freeze"])
def growth_sources(expected):
 require(type(expected) is str and re.fullmatch(r"[0-9a-f]{40}",expected),"GROWTH_D")
 repo=Path(__file__).resolve().parents[2]
 def git(*args):
  value=subprocess.run(["git","-c","maintenance.auto=false","-c","gc.auto=0",*args],
cwd=repo,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
  require(value.returncode==0,"GROWTH_SOURCE")
  return value.stdout
 require(git("rev-parse","HEAD").decode().strip()==expected and expected!=C,"GROWTH_D_HEAD")
 git("diff","--quiet","HEAD")
 git("merge-base","--is-ancestor",C,expected)
 git("merge-base","--is-ancestor",TERM_C,expected)
 require(expected!=TERM_C,"GROWTH_TERM_D")
 git("merge-base","--is-ancestor",DR_A,DR_C)
 git("merge-base","--is-ancestor",DR_C,expected)
 require(expected!=DR_C,"GROWTH_RESUME_D")
 git("merge-base","--is-ancestor",DRV2_A,DRV2_C)
 git("merge-base","--is-ancestor",DRV2_C,expected)
 require(expected!=DRV2_C,"GROWTH_RESUME_V2_D")
 git("merge-base","--is-ancestor",MB_A,MB_C)
 git("merge-base","--is-ancestor",MB_C,expected)
 require(expected!=MB_C,"GROWTH_MAPS_BUDGET_D")
 git("merge-base","--is-ancestor",WORK_A,WORK_C)
 git("merge-base","--is-ancestor",WORK_C,expected)
 require(expected!=WORK_C,"GROWTH_SCAN_WORK_D")
 git("merge-base","--is-ancestor",DRIFT_REPAIR,DRIFT_A)
 git("merge-base","--is-ancestor",DRIFT_A,DRIFT_C)
 git("merge-base","--is-ancestor",DRIFT_C,expected)
 require(expected!=DRIFT_C,"GROWTH_DRIFT_RESUME_D")
 git("merge-base","--is-ancestor",MINIMAL_A,MINIMAL_C)
 git("merge-base","--is-ancestor",MINIMAL_C,expected)
 require(expected!=MINIMAL_C,"GROWTH_MINIMAL_D")
 git("merge-base","--is-ancestor",SERIAL_A,SERIAL_C)
 git("merge-base","--is-ancestor",SERIAL_C,expected)
 require(expected!=SERIAL_C,"GROWTH_SERIAL_D")
 git("merge-base","--is-ancestor",SYSTEMCTL_A,SYSTEMCTL_C)
 git("merge-base","--is-ancestor",SYSTEMCTL_C,expected)
 require(expected!=SYSTEMCTL_C,"GROWTH_SYSTEMCTL_D")
 for path,sha in history.c.SYSTEMCTL_BASELINE["documents_sha256"].items():
  require(digest(git("show",expected+":"+path))==sha,"GROWTH_SYSTEMCTL_A_CHANGED")
 decision=history.c.SYSTEMCTL_OWNER_DECISION
 require(digest(git("show",expected+":"+decision["record_path"]))==decision["record_sha256"],
"GROWTH_SYSTEMCTL_B_CHANGED")
 git("merge-base","--is-ancestor",TEMPLATE_A,TEMPLATE_C)
 git("merge-base","--is-ancestor",TEMPLATE_C,expected)
 require(expected!=TEMPLATE_C,"GROWTH_TEMPLATE_D")
 for path,sha in history.c.TEMPLATE_BASELINE["documents_sha256"].items():
  require(digest(git("show",expected+":"+path))==sha,"GROWTH_TEMPLATE_A_CHANGED")
 decision=history.c.TEMPLATE_OWNER_DECISION
 require(digest(git("show",expected+":"+decision["record_path"]))==decision["record_sha256"],
"GROWTH_TEMPLATE_B_CHANGED")
 git("merge-base","--is-ancestor",NAMES_A,NAMES_C)
 git("merge-base","--is-ancestor",NAMES_C,expected)
 require(expected!=NAMES_C,"GROWTH_NAMES_D")
 for authority in (history.c.NAMES_BASELINE,history.c.NAMES_CLOSURE):
  require(git("rev-parse",authority["commit"]+"^{tree}").decode().strip()==authority["tree"],
"GROWTH_NAMES_TREE")
 for path,sha in history.c.NAMES_BASELINE["documents_sha256"].items():
  for commit in (NAMES_A,NAMES_C,expected):
   require(digest(git("show",commit+":"+path))==sha,"GROWTH_NAMES_A_CHANGED")
 decision=history.c.NAMES_OWNER_DECISION
 for commit in (NAMES_C,expected):
  require(digest(git("show",commit+":"+decision["record_path"]))==decision["record_sha256"],
"GROWTH_NAMES_B_CHANGED")
 git("merge-base","--is-ancestor",EXEC_A,EXEC_C)
 git("merge-base","--is-ancestor",EXEC_C,expected)
 require(expected!=EXEC_C,"GROWTH_EXEC_D")
 for authority in (history.c.EXEC_BASELINE,history.c.EXEC_CLOSURE):
  require(git("rev-parse",authority["commit"]+"^{tree}").decode().strip()==authority["tree"],
"GROWTH_EXEC_TREE")
 for path,sha in history.c.EXEC_BASELINE["documents_sha256"].items():
  for commit in (EXEC_A,EXEC_C,expected):
   require(digest(git("show",commit+":"+path))==sha,"GROWTH_EXEC_A_CHANGED")
 decision=history.c.EXEC_OWNER_DECISION
 for commit in (EXEC_C,expected):
  require(digest(git("show",commit+":"+decision["record_path"]))==decision["record_sha256"],
"GROWTH_EXEC_B_CHANGED")
 git("merge-base","--is-ancestor",GS_A,GS_C)
 git("merge-base","--is-ancestor",GS_C,expected)
 require(expected!=GS_C,"GROWTH_GS_D")
 for authority in (history.c.GS_BASELINE,history.c.GS_CLOSURE):
  require(git("rev-parse",authority["commit"]+"^{tree}").decode().strip()==authority["tree"],
"GROWTH_GS_TREE")
 for path,sha in history.c.GS_BASELINE["documents_sha256"].items():
  for commit in (GS_A,GS_C,expected):
   require(digest(git("show",commit+":"+path))==sha,"GROWTH_GS_A_CHANGED")
 decision=history.c.GS_OWNER_DECISION
 for commit in (GS_C,expected):
  require(digest(git("show",commit+":"+decision["record_path"]))==decision["record_sha256"],
"GROWTH_GS_B_CHANGED")
 git("merge-base","--is-ancestor",QI_A,QI_C)
 git("merge-base","--is-ancestor",QI_C,expected)
 require(expected!=QI_C,"GROWTH_QI_D")
 for authority in (history.c.QI_BASELINE,history.c.QI_CLOSURE):
  require(git("rev-parse",authority["commit"]+"^{tree}").decode().strip()==authority["tree"],"GROWTH_QI_TREE")
 for path,sha in history.c.QI_BASELINE["documents_sha256"].items():
  for commit in (QI_A,QI_C,expected):
   require(digest(git("show",commit+":"+path))==sha,"GROWTH_QI_A_CHANGED")
 decision=history.c.QI_OWNER_DECISION
 for commit in (QI_C,expected):
  require(digest(git("show",commit+":"+decision["record_path"]))==decision["record_sha256"],"GROWTH_QI_B_CHANGED")
 git("merge-base","--is-ancestor",DS_A,DS_C)
 git("merge-base","--is-ancestor",DS_C,expected)
 require(expected!=DS_C,"GROWTH_DS_D")
 for authority in (history.c.DS_BASELINE,history.c.DS_CLOSURE):
  require(git("rev-parse",authority["commit"]+"^{tree}").decode().strip()==authority["tree"],"GROWTH_DS_TREE")
 for path,sha in history.c.DS_BASELINE["documents_sha256"].items():
  for commit in (DS_A,DS_C,expected):
   require(digest(git("show",commit+":"+path))==sha,"GROWTH_DS_A_CHANGED")
 decision=history.c.DS_OWNER_DECISION
 for commit in (DS_C,expected):
  require(digest(git("show",commit+":"+decision["record_path"]))==decision["record_sha256"],"GROWTH_DS_B_CHANGED")
 for prefix,a,b in (("VM_ADOPTION",VM_A,VM_C),("RUNTIME",RT_A,RT_C),("HOST_FD",FD_A,FD_C),("USAGE",UC_A,UC_C),("TRANSPORT",TC_A,TC_C),("RESUMED_VM",RC_A,RC_C)):
  baseline,decision,closure=(getattr(history.c,prefix+suffix) for suffix in ("_BASELINE","_OWNER_DECISION","_CLOSURE"))
  require(all(row is None for row in (baseline,decision,closure)) or all(type(row) is dict for row in (baseline,decision,closure)),"GROWTH_"+prefix+"_AUTHORITY_PARTIAL")
  if baseline is None:continue
  require(a==baseline["commit"] and b==closure["commit"] and expected!=b,"GROWTH_"+prefix+"_AUTHORITY")
  git("merge-base","--is-ancestor",a,b)
  git("merge-base","--is-ancestor",b,expected)
  for authority in (baseline,closure):
   require(git("rev-parse",authority["commit"]+"^{tree}").decode().strip()==authority["tree"],"GROWTH_"+prefix+"_TREE")
  for path,sha in baseline["documents_sha256"].items():
   for commit in (a,b,expected):
    require(digest(git("show",commit+":"+path))==sha,"GROWTH_"+prefix+"_A_CHANGED")
  for commit in (b,expected):
   require(digest(git("show",commit+":"+decision["record_path"]))==decision["record_sha256"],"GROWTH_"+prefix+"_B_CHANGED")
 for path,sha in history.c.SERIAL_BASELINE["documents_sha256"].items():
  require(digest(git("show",expected+":"+path))==sha,"GROWTH_SERIAL_A_CHANGED")
 decision=history.c.SERIAL_OWNER_DECISION
 require(digest(git("show",expected+":"+decision["record_path"]))==decision["record_sha256"],
"GROWTH_SERIAL_B_CHANGED")
 for name,sha in zip(DOC_PINS,MINIMAL_PINS):
  require(digest(git("show",expected+":docs/a2-execution/q2-core-minimal-continuation/"+name))==sha,
"GROWTH_MINIMAL_A_CHANGED")
 for name,sha in zip(DOC_PINS,DRIFT_PINS):
  require(digest(git("show",expected+":docs/a2-execution/q2-core-journal-drift-resume/"+name))==sha,
"GROWTH_DRIFT_RESUME_A_CHANGED")
 for name,sha in zip(DOC_PINS,WORK_PINS):
  require(digest(git("show",expected+":docs/a2-execution/q2-core-journal-scan-work/"+name))==sha,
"GROWTH_SCAN_WORK_A_CHANGED")
 for name,sha in zip(DOC_PINS,MB_PINS):
  require(digest(git("show",expected+":docs/a2-execution/q2-core-journal-maps-budget/"+name))==sha,
"GROWTH_MAPS_BUDGET_A_CHANGED")
 for name,sha in zip(DOC_PINS,DRV2_PINS):
  require(digest(git("show",expected+":docs/a2-execution/q2-core-journal-diagnostic-resume-v2/"+name))==sha,
"GROWTH_RESUME_V2_A_CHANGED")
 for name,sha in zip(DOC_PINS,DR_PINS):
  require(digest(git("show",expected+":docs/a2-execution/q2-core-journal-diagnostic-resume/"+name))==sha,
"GROWTH_RESUME_A_CHANGED")
 for name,sha in DOC_PINS.items():
  require(digest(git("show",expected+":docs/a2-execution/q2-core-journal-growth/"+name))==sha,
"GROWTH_A_CHANGED")
 for name,sha in zip(DOC_PINS,READ_PINS):
  require(digest(git("show",expected+":docs/a2-execution/q2-core-journal-host-read/"+name))==sha,
"GROWTH_READ_A_CHANGED")
 names=("q2_journal_growth.py","q2_journal_growth_guest.py","q2_core_capacity_capture.py",
"q2_core_capacity_reader.py","q2_sshd_source_capture.py","q2_sshd_source_reader.py",
"q2_core_obligation_inputs.py","q2_core_prior_attempt.py","q2_core_delivery_contract.py",
"q2_local_source_delivery.py","q2_core_approved_inputs.py","q2_host_kernel_facts.py","q2_journal_retained_fds.py")
 exporter=git("show",expected+":tests/e3_host/q2_host_export.py")
 require((len(exporter),digest(exporter))==Q1_EXPORT_PIN,"GROWTH_Q1_EXPORT_SOURCE")
 sources={}
 for name in names:
  fd=os.open(Path(__file__).with_name(name),os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME|os.O_CLOEXEC)
  try:
   raw,_=local.stable_read(fd,524288,lambda:None)
  finally:
   os.close(fd)
  require(raw==git("show",expected+":tests/e3_host/"+name),"GROWTH_SOURCE_DRIFT")
  if name not in (*names[:2],"q2_core_prior_attempt.py","q2_core_delivery_contract.py","q2_core_approved_inputs.py","q2_journal_retained_fds.py"):
   require(raw==git("show","8e91fa2631aa18a8469efa5a14e4145eaf781e28:tests/e3_host/"+name),
"GROWTH_DEPENDENCY_CHANGED")
  sources[name]=raw
 require(all(len(sources[name])<=98304 for name in names[:2]),"GROWTH_SOURCE_LIMIT")
 require(len(sources["q2_journal_retained_fds.py"])<=16384,"GROWTH_CUSTODY_SOURCE_LIMIT")
 return sources
class GrowthAnchor(prior.Anchor):
 custody=None
 def start_custody(self,commit,nonce,sources,frozen):
  require(self.custody is None,"GROWTH_CUSTODY_NO_RESTART")
  self.custody=custody.Custodian(self,history.previous_maintenance_pins(),commit=commit,nonce=nonce,
source_sha256=digest(sources["q2_journal_retained_fds.py"]),history_sha256=resume_sha256(frozen["source_binding"]["resume"]))
  self.previous_files=frozen["previous_maintenance_files"]
 def recheck(self,*,after_create=False):
  super().recheck(after_create=after_create)
  if self.custody is not None:self.custody.check(after_create)
 def close(self):
  try:super().close()
  finally:
   if self.custody is not None:
    held,self.custody=self.custody,None
    self.custody_exit=held.close()
 def capacity(self):
  Store(self.fd,self.deadline.check).capacity()
 def growth_inputs(self,frozen,sources):
  self.bind_retained()
  frozen["start_raw"]=self.raw["start.sh"]
  frozen["capacity_files"]={}
  for suffix,(size,sha) in CAPACITY_PINS.items():
   name=".lhqcap-20261006a."+suffix
   fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME|os.O_CLOEXEC,dir_fd=self.fd)
   self.held.append((name,fd,local.metadata(os.fstat(fd))))
   validate_file(os.fstat(fd),65536,self.info["uid"])
   require(os.fstat(fd).st_gid==self.info["gid"] and os.fstat(fd).st_dev==self.info["dev"]
and len({(os.fstat(x).st_dev,os.fstat(x).st_ino) for _,x,_ in self.held})==len(self.held),
"GROWTH_CAPACITY_IDENTITY")
   raw,_=local.stable_read(fd,65536,self.deadline.check)
   require((len(raw),digest(raw))==(size,sha),"GROWTH_CAPACITY_PIN")
   frozen["capacity_files"][name]=raw
   if suffix=="stdout":
    frozen["saved_rows"]=prior.validate_result(raw,digest(sources["q2_core_capacity_reader.py"]),
frozen["description"])["rows"]
  units={row["name"]:row for row in frozen["inventory"]["expected_units"]}
  for session in GROWTH_CORE_SESSIONS:
   name="."+session+".stdout"
   fd=next(fd for held,fd,_ in self.held if held==name)
   raw=os.pread(fd,65536,0)
   require(raw.startswith(b"LHCHLO1\n") and int.from_bytes(raw[8:16],"big")==len(raw)-16,
"GROWTH_HELLO_FRAME")
   hello=prior.r.parse(raw[16:],65536)
   carrier=hello["carrier_unit"]
   require(hello["guest_boot_id"]==frozen["boot_id"] and carrier["name"] in units,
"GROWTH_HELLO_BINDING")
   units[carrier["name"]]["control_group"]=carrier["control_group"]
  frozen["previous_maintenance_files"]={}
  frozen["previous_maintenance_identities"]=[]
  for name,(size,sha) in history.previous_maintenance_pins().items():
   self.deadline.check()
   fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=self.fd)
   info=os.fstat(fd)
   self.held.append((name,fd,local.metadata(info)))
   validate_file(info,65536,self.info["uid"])
   require(info.st_gid==self.info["gid"] and info.st_dev==self.info["dev"]
and len({(os.fstat(x).st_dev,os.fstat(x).st_ino) for _,x,_ in self.held})==len(self.held),
"GROWTH_PREVIOUS_IDENTITY")
   raw,_=local.stable_read(fd,65536,self.deadline.check)
   require((len(raw),digest(raw))==(size,sha),"GROWTH_PREVIOUS_PIN")
   frozen["previous_maintenance_files"][name]=raw
   frozen["previous_maintenance_identities"].append(dict(basename=name,metadata=local.metadata(info),bytes=size,sha256=sha))
  frozen["source_binding"]["guest_startup_assurance"]=validate_startup_assurance(frozen.get("guest_startup_assurance"))
  frozen["source_binding"]["resume"]=history.build_previous_maintenance(frozen["previous_maintenance_files"])
  self.previous_maintenance_recheck()
  frozen["source_binding"]["inventory_sha256"]=digest(canonical(frozen["inventory"]))
  frozen["source_binding_sha256"]=digest(canonical(frozen["source_binding"]))
  validate_q1_frozen(frozen)
  self.recheck()
 def previous_maintenance_recheck(self):
  # Held metadata is checked by recheck; this bounded reread binds bytes immediately
  # before consumption as well as during ordinary preflight. No directory scan.
  if self.custody is not None:
   self.custody.check(self.custody.after_create)
   files=self.previous_files
  else:
   files={}
   for name,(size,sha) in history.previous_maintenance_pins().items():
    fd=next(fd for held,fd,_ in self.held if held==name)
    self.deadline.check()
    os.lseek(fd,0,os.SEEK_SET)
    raw,_=local.stable_read(fd,65536,self.deadline.check)
    require((len(raw),digest(raw))==(size,sha),"GROWTH_PREVIOUS_PIN")
    files[name]=raw
  for fixed in history.previous_journal_profiles():
   for suffix in history.PREVIOUS_JOURNAL_ABSENT:
    self.absent("."+fixed["session"]+"."+suffix)
  history.build_previous_maintenance(files)
def _check_management_budget(cpu,rss,*,stage,cpu_limit,components):
 if cpu<=cpu_limit and rss<=512*MIB:
  return
 error=prior.r.ObservationError("GROWTH_MANAGEMENT_BUDGET")
 error.diagnostic=dict(operation="management_budget",stage=stage,
cpu=dict(actual=cpu,limit=cpu_limit,unit="seconds" if stage=="management_usage" else "nanoseconds",
exceeded=cpu>cpu_limit),
rss=dict(actual=rss,limit=512*MIB,unit="bytes",exceeded=rss>512*MIB),components=components)
 raise error
def _usage_failure(item,stage,error):
 # Reuse the command identity already held in memory. Never include argv,
 # raw proc content, exception text/paths, or perform another observation.
 binding=getattr(item,"identity",{})
 if type(binding) is not dict:binding={}
 argv_sha=binding.get("argv_sha256")
 start=binding.get("starttime")
 reason=error.args[0] if error.args else None
 number=getattr(error,"errno",None)
 return dict(pid=item.process.pid,stage=stage,error_type=type(error).__name__[:64],
 errno=number if type(number) is int else None,
 reason=reason if type(reason) is str and re.fullmatch(r"GROWTH_[A-Z0-9_]{1,80}",reason) else None,
 identity=dict(argv_sha256=argv_sha if type(argv_sha) is str and re.fullmatch(r"[0-9a-f]{64}",argv_sha) else None,
 starttime=start if type(start) is int and start>0 else None))
def command_usage(pid,raw):
 # One kernel stat record includes CPU and RSS even during exit. An unreaped
 # Popen child cannot recycle its PID; bind its start time below as well.
 head,sep,tail=raw.rpartition(b") ")
 fields=tail.split()
 require(sep and head.startswith(str(pid).encode()+b" (") and len(fields)>=22
and fields[0] in (b"R",b"S",b"D",b"T",b"t",b"Z",b"X",b"x",b"K",b"W",b"P",b"I")
and all(fields[i].isdigit() and len(fields[i])<=20 for i in (11,12,19,21)),"GROWTH_USAGE_STAT")
 start=int(fields[19])
 require(start>0,"GROWTH_USAGE_STAT")
 return start,(int(fields[11])+int(fields[12]))/os.sysconf("SC_CLK_TCK"),int(fields[21])*os.sysconf("SC_PAGE_SIZE")
def management_usage():
 live=[item for item in COMMANDS if not item.is_vm and item.process.poll() is None]
 require(len(live)+len(custody.ACTIVE)<=8,"GROWTH_CHILD_BUDGET")
 own,children=(resource.getrusage(kind) for kind in (resource.RUSAGE_SELF,resource.RUSAGE_CHILDREN))
 cpu=own.ru_utime+own.ru_stime+children.ru_utime+children.ru_stime
 rss=own.ru_maxrss*1024
 complete=True
 failures=[]
 for item in live:
  stage="stat_read"
  try:
   raw=custody.proc(item.process.pid,"stat",4096)
   stage="stat_parse"
   start,used,resident=command_usage(item.process.pid,raw)
   stage="process_identity"
   binding=getattr(item,"identity",None)
   require(type(binding) is dict and binding.get("pid")==item.process.pid
and (binding.get("starttime") is None or type(binding["starttime"]) is int and binding["starttime"]==start),"GROWTH_USAGE_IDENTITY")
   binding["starttime"]=start
   cpu+=used;rss+=resident
  except (OSError,ValueError,RuntimeError) as error:
   if item.process.poll() is None or stage=="process_identity":
    complete=False
    failures.append(_usage_failure(item,stage,error))
   else:
    current=resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu+=current.ru_utime+current.ru_stime-children.ru_utime-children.ru_stime
    children=current
 for item in custody.ACTIVE:
  used,resident=item.usage();cpu+=used;rss+=resident
 _check_management_budget(cpu,rss,stage="management_usage",cpu_limit=120,
components=dict(self_cpu_seconds=own.ru_utime+own.ru_stime,
exited_children_cpu_seconds=children.ru_utime+children.ru_stime,
self_peak_rss_bytes=own.ru_maxrss*1024,live_non_vm_rss_bytes=rss-own.ru_maxrss*1024,
live_children=len(live)+len(custody.ACTIVE),live_rss_complete=complete))
 if not complete:
  error=prior.r.ObservationError("GROWTH_USAGE_UNKNOWN")
  error.diagnostic=dict(operation="management_usage",stage="live_child_observation",
 complete=False,live_children=len(live)+len(custody.ACTIVE),failed_children=failures)
  raise error
 return dict(cpu_seconds=cpu,rss_upper_observation_bytes=rss,complete=True,
live_children=len(live)+len(custody.ACTIVE),vm_excluded=True,guest_aggregate="UNKNOWN")
class Usage:
 def __init__(self,previous=None):
  self.previous=previous or dict(cpu_nanoseconds=0,rss_peak_bytes=0)
  self.last=dict(self.previous)
 def sample(self):
  value=management_usage()
  cpu=self.previous["cpu_nanoseconds"]+int(value["cpu_seconds"]*1000000000+1)
  children_rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024
  rss=max(self.last["rss_peak_bytes"],value["rss_upper_observation_bytes"],children_rss)
  _check_management_budget(cpu,rss,stage="usage_sample",cpu_limit=120000000000,
components=dict(previous_cpu_nanoseconds=self.previous["cpu_nanoseconds"],
current_cpu_nanoseconds=cpu-self.previous["cpu_nanoseconds"],
previous_rss_peak_bytes=self.previous["rss_peak_bytes"],last_rss_peak_bytes=self.last["rss_peak_bytes"],
management_rss_bytes=value["rss_upper_observation_bytes"],exited_children_peak_rss_bytes=children_rss))
  self.last=dict(cpu_nanoseconds=cpu,rss_peak_bytes=rss)
  return dict(self.last)
def resume_sha256(resume):
 # Preserve the complete validated history elsewhere; hash its canonical bytes,
 # including the LF, only for the bounded short preflight representation.
 history.validate_maintenance_resume(resume)
 return digest(canonical(resume))
def make_preflight(commit,manifest,window,nonce,usage,*,resume):
 value=dict(schema="lhq-journal-growth-preflight/v15",R=R,A=RC_A,C=RC_C,D=commit,manifest_sha256=manifest,
window_binding=window,nonce=nonce,usage=usage,window_seconds=900,change_seconds=780,resume_sha256=resume_sha256(resume))
 return parse_preflight(canonical(value))
def parse_preflight(raw):
 value=prior.r.parse(raw,4096)
 require(type(value) is dict and set(value)=={"schema","R","A","C","D","manifest_sha256","window_binding",
"nonce","usage","window_seconds","change_seconds","resume_sha256"} and value["schema"]=="lhq-journal-growth-preflight/v15",
"GROWTH_PREFLIGHT_SCHEMA")
 require(value["R"]==R and value["A"]==RC_A and value["C"]==RC_C,"GROWTH_PREFLIGHT_AUTHORITY")
 require(type(value["D"]) is str and re.fullmatch("[0-9a-f]{40}",value["D"]),"GROWTH_PREFLIGHT_D")
 for field in ("manifest_sha256","nonce","resume_sha256"):
  require(type(value[field]) is str and re.fullmatch("[0-9a-f]{64}",value[field]),"GROWTH_PREFLIGHT_DIGEST")
 require(value["window_seconds"]==900 and type(value["window_seconds"]) is int
and value["change_seconds"]==780 and type(value["change_seconds"]) is int,"GROWTH_PREFLIGHT_DEADLINE")
 require(value["resume_sha256"]==resume_sha256(history.maintenance_resume()),"GROWTH_PREFLIGHT_HISTORY")
 usage=value["usage"]
 require(type(usage) is dict and set(usage)=={"cpu_nanoseconds","rss_peak_bytes"},"GROWTH_PREFLIGHT_USAGE")
 for key,cap in (("cpu_nanoseconds",120000000000),("rss_peak_bytes",512*MIB)):
  require(type(usage[key]) is int and 0<usage[key]<=cap,"GROWTH_PREFLIGHT_USAGE")
 window=value["window_binding"]
 require(type(window) is dict and set(window)=={"boot_id","origins"}
and type(window["origins"]) is list and len(window["origins"])==2
and all(type(x) is int and x>0 for x in window["origins"]),"GROWTH_PREFLIGHT_WINDOW")
 from e3_host.q2_journal_growth_guest import uuid_value
 uuid_value(window["boot_id"])
 return value
class Maintenance:
 def __init__(self,anchor,inputs,frozen,sources,vm,tools,window,commit,usage=None,nonce=None):
  self.anchor,self.inputs,self.frozen,self.sources=anchor,inputs,frozen,sources
  self.vm,self.tools,self.window,self.commit=vm,tools,window,commit
  self.store=Store(anchor.fd,self.check)
  self.transports,self.new_vm=[],None
  self.nonce=nonce or os.urandom(32).hex()
  self.usage=usage or Usage()
  self.seq=Sequence(self.boundary,self.event)
  self.pending=[]
  self.result=dict(schema="lhq-journal-growth-receipt/v16",session=SESSION,R=R,A=RC_A,C=RC_C,D=commit,
nonce=self.nonce,resume=history.maintenance_resume(),guest_startup_assurance=validate_startup_assurance(self.frozen.get("guest_startup_assurance")),access_mode=ACCESS_MODE,host_writer_observation="NOT_PERFORMED",continuous_exclusion_proven=False,
state="LOCAL_CHECKED",marker_created=False,ssh_requests=0,business_cases=0,
production_supported=False,old_commitments_refunded=False,exclusive_reservation_proven=False,
original_boot_id=frozen["boot_id"],remote_exit="UNKNOWN",serial_capture="NOT_CAPTURED_NULL_BACKEND")
 def check(self):
  self.window.check()
  self.usage.sample()
 def boundary(self):
  self.check()
  self.store.capacity()
  self.store.budget()
  self.vm["images"].capacity()
 def bindings(self):
  self.inputs.recheck(self.check)
  recheck_q1_inputs(self.inputs,self.frozen,self.check)
  recheck_vm_activation(self.inputs,self.frozen,self.check)
  history.recheck_local_preflight(self.inputs,self.frozen,self.check)
  history.recheck_transport_failure(self.inputs,self.frozen,self.check)
  validate_q1_frozen(self.frozen)
  self.anchor.recheck(after_create=bool(self.store.opened))
  self.anchor.previous_maintenance_recheck()
  history.validate_maintenance_resume(self.frozen["source_binding"]["resume"])
  self.vm["images"].recheck()
  for tool in self.tools.values():
   tool.recheck()
 def event(self,value):
  if "consumed.json" not in self.store.opened:
   self.pending.append(value)
  else:
   self.store.event(value)
 def manifest(self):
  self.bindings()
  return dict(schema="lhq-journal-growth-manifest/v16",R=R,A=RC_A,C=RC_C,D=self.commit,
nonce=self.nonce,resume=history.maintenance_resume(),guest_startup_assurance=validate_startup_assurance(self.frozen.get("guest_startup_assurance")),access_mode=ACCESS_MODE,host_writer_observation="NOT_PERFORMED",continuous_exclusion_proven=False,
historical_authority=dict(A=A,C=C,observer_superseded_by=MINIMAL_A,minimal_C=MINIMAL_C,serial_A=SERIAL_A,serial_C=SERIAL_C,systemctl_A=SYSTEMCTL_A,systemctl_C=SYSTEMCTL_C,template_A=TEMPLATE_A,template_C=TEMPLATE_C,names_A=NAMES_A,names_C=NAMES_C,exec_A=EXEC_A,exec_C=EXEC_C),inputs=history.encode_manifest_inputs(self.frozen["source_binding"]),
custody_binding=self.anchor.custody.binding,
window_binding=self.window.binding,
inventory_sha256=digest(canonical(self.frozen["inventory"])),
retained_sha256=digest(canonical(self.anchor.retained)),
sources={name:dict(bytes=len(raw),sha256=digest(raw)) for name,raw in self.sources.items()},
tools={name:tool.binding() for name,tool in self.tools.items()},
vm=self.vm["binding"],image_identities=self.vm["images"].image_keys(),
original_argv=self.vm["original_argv"],restart_argv=self.vm["restart_argv"],
image_commands=image_commands(self.vm["images"].journal_path,
self.anchor.path+"/"+NAMES["journal.backup.qcow2"]),
protocol="two fixed phases; post bound to the durably saved pre report; no probe or retry")
 def preflight(self):
  self.store.absent()
  host_fd_admission(self.anchor.fd,self.check,"preflight")
  self.store.capacity()
  self.vm["process"].recheck()
  self.vm["images"].capacity()
  desc=growth_descriptor(self.frozen,self.nonce,"pre",self.window)
  argv=remote_argv(self.anchor.path,self.sources,desc)
  self.pre_description,self.pre_argv=desc,argv
  result=run_tool(argv[:1]+["-G"]+argv[1:],self.check,
executable=f"/proc/self/fd/{self.anchor.ssh}",pass_fds=(self.anchor.ssh,),limit=65536)
  require(len(result["stderr"])<=4096,"GROWTH_SSH_OPTIONS")
  return self.manifest()
 def transport(self,phase,pre=None):
  self.window.change()
  self.bindings()
  require(len(self.transports)==(0 if phase=="pre" else 1),"GROWTH_SSH_COUNT")
  desc=self.pre_description if phase=="pre" else growth_descriptor(self.frozen,self.nonce,phase,self.window,pre)
  argv=self.pre_argv if phase=="pre" else remote_argv(self.anchor.path,self.sources,desc)
  self.event(dict(phase=phase,argv_sha256=digest(canonical(argv)),description_sha256=digest(canonical(desc)),
window_seconds=desc["window_seconds"],change_seconds=desc["change_seconds"]))
  self.result["ssh_requests"]+=1
  from e3_host import q2_journal_growth_guest as guest
  validate=guest.validate_pre_report if phase=="pre" else guest.validate_post_report
  transport=MaintenanceTransport(self.anchor,self.store,argv,phase,self.nonce,
self.frozen["source_binding_sha256"],self.frozen["boot_id"],self.check,
validate=lambda report:validate(report,desc))
  self.transports.append(transport)
  return transport
 def run(self,manifest):
  images,old,img,qemu=self.vm["images"],self.vm["process"],self.tools["image"],self.tools["qemu"]
  try:
   def consume():
    self.window.change(); self.bindings(); self.store.absent(); self.store.capacity()
    host_fd_admission(self.anchor.fd,self.check,"before_marker")
    self.store.put("consumed.json",canonical(dict(manifest_sha256=digest(canonical(manifest)),
manifest=manifest,resume_sha256=resume_sha256(history.maintenance_resume()),nonce=self.nonce,clocks=self.window.origins,session=SESSION,D=self.commit,
access_mode=ACCESS_MODE,host_writer_observation="NOT_PERFORMED",continuous_exclusion_proven=False,
guest_startup_assurance=validate_startup_assurance(self.frozen.get("guest_startup_assurance")),
pre_command_sha256=digest(canonical(self.pre_argv)),
post_command_derivation="same fixed sources; post descriptor bound to saved canonical pre report",
pre_description=self.pre_description)))
    self.result["marker_created"]=True
    for row in self.pending:
     self.store.event(row)
    self.pending.clear()
    return dict(manifest_sha256=digest(canonical(manifest)))
   self.seq.step("CONSUMED",consume)
   pre=self.seq.step("GUEST_QUIET",lambda:self.transport("pre").receive_report())
   def poweroff():
    self.window.change(); self.bindings(); old.recheck()
    remote_argv(self.anchor.path,self.sources,
growth_descriptor(self.frozen,self.nonce,"post",self.window,pre))
    self.transports[0].continue_poweroff(digest(canonical(pre)))
    captured=self.transports[0].finish()
    while not old.exited():
     self.check(); time.sleep(min(.1,self.window.remaining()))
    images.checkpoint()
    return dict(transport=captured,pidfd_exit=True,image=images.offline_info(img,OLD_SIZE))
   self.seq.step("POWERED_OFF",poweroff)
   def backup():
    self.window.change(); self.bindings()
    return full_backup(self.store,images.journal_fd)
   self.seq.step("BACKED_UP",backup)
   def grow():
    self.window.change(); self.bindings()
    self.store.capacity()
    images.capacity()
    return images.grow(img,self.anchor.path+"/"+NAMES["journal.backup.qcow2"])
   self.seq.step("IMAGE_GROWN",grow)
   def boot():
    self.window.change(); self.bindings()
    images.capacity()
    require(old.exited(),"GROWTH_OLD_VM_ALIVE")
    self.anchor.absent(NAMES["vm.pid"])
    launched=qemu.run(self.vm["restart_argv"][1:],vm=True)
    pid=pidfile(self.anchor.fd,NAMES["vm.pid"],self.check)
    self.new_vm=ProcessIdentity(pid,self.vm["restart_argv"],qemu.fd,self.check)
    fd=os.open(NAMES["vm.pid"],os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME|os.O_CLOEXEC,
dir_fd=self.anchor.fd)
    self.store.opened["vm.pid"]=fd
    self.store.budget(); images.recheck()
    waited=time.monotonic()
    while time.monotonic()-waited<60:
     self.check(); self.new_vm.recheck(); time.sleep(min(.1,self.window.remaining()))
    return dict(process=self.new_vm.recheck(),returncode=launched["returncode"],passive_wait_seconds=60)
   self.seq.step("BOOTED",boot)
   def filesystem():
    self.new_vm.recheck()
    transport=self.transport("post",pre)
    report=transport.receive_report()
    self.result["post_transport"]=transport.finish()
    return report
   post=self.seq.step("FILESYSTEM_GROWN",filesystem)
   def verify():
    from e3_host import q2_journal_growth_guest as guest
    self.bindings(); self.new_vm.recheck()
    require(post["pre_report_sha256"]==digest(canonical(pre)),"GROWTH_POST_BINDING")
    guest.verify_preservation(pre["tree"],post["tree"])
    guest.validate_completion(pre["rows"],post["rows"])
    comparison=prior.compare(dict(rows=post["rows"]),self.frozen["horizon"])
    require(all(row[field]["deficit"]==0 for row in comparison["pools"]
for field in ("bytes","inodes")),"GROWTH_OTHER_CAPACITY")
    self.result.update(new_boot_id=post["boot_id"],remote_exit="HELPER_REPORTED_COMPLETE",
new_vm=self.new_vm.recheck(),image_identities=images.image_keys())
    return dict(comparison=comparison,tree=post["tree"],rows=post["rows"])
   self.seq.step("VERIFIED",verify)
   self.result.update(state="VERIFIED",reason="MAINTENANCE_COMPLETE")
  except (Exception,KeyboardInterrupt) as error:
   self.result.update(state="STOP_AND_RETAIN",reason=prior.safe_reason(error),
error_type=type(error).__name__,errno=getattr(error,"errno",None),
diagnostic=getattr(error,"diagnostic",{}))
   failed=getattr(error,"growth_result",None)
   if failed is not None:
    self.result["failed_tool"]=dict(returncode=failed["returncode"],eof=failed["eof"],
streams={name:dict(bytes=len(failed[name]),sha256=digest(failed[name]))
for name in ("stdout","stderr")})
  self.result.update(last_step=self.seq.state,started=sorted(self.seq.started),
clock_origins_ns=self.window.origins)
  self.result.update(kernel_report=self.window.kernel_report,manifest_sha256=digest(canonical(manifest)))
  self.result["processes"]=[dict(identity=getattr(item,"identity",dict(pid=item.process.pid)),
exit=item.process.poll(),vm=item.is_vm) for item in COMMANDS]
  self.result["transports"]=[dict(pid=item.process.pid,exit=item.process.poll(),
files={name:dict(bytes=len(raw),sha256=digest(bytes(raw))) for name,raw in item.output.items()})
for item in self.transports]
  self.result["marker_created"]="consumed.json" in self.store.opened
  try:
   self.check()
   self.bindings()
   self.result.update(budget=self.store.budget(),management_usage=self.usage.sample(),
retained_custody=self.anchor.custody.summary())
   if "consumed.json" in self.store.opened:
    self.store.put("receipt.json",canonical(self.result))
  except (Exception,KeyboardInterrupt):
   self.result.update(state="UNKNOWN" if self.result["marker_created"] else "STOP_AND_RETAIN",seal="INCOMPLETE")
  return self.result
def main():
 parser=argparse.ArgumentParser()
 for name in ("frame","plan-archive","archives-dir","expected-commit","expected-manifest","window-binding","preflight","q1-sources","vm-activation","local-preflight","transport-failure"):
  parser.add_argument("--"+name)
 parser.add_argument("--execute",action="store_true")
 parser.add_argument("--trusted-single-admin",action="store_true")
 parser.add_argument("--trusted-guest-startup",action="store_true")
 args=parser.parse_args()
 if not all((args.frame,args.plan_archive,args.archives_dir,args.expected_commit)):
  print(canonical(field_readiness()).decode("ascii"),end="")
  return 3
 inputs,anchor,vm,maintenance,tools=prior.Inputs(),None,None,None,{}
 window=None
 usage=None
 global VM_LIMITS
 VM_LIMITS={key:resource.getrlimit(key) for key in (resource.RLIMIT_AS,resource.RLIMIT_NOFILE)}
 released=False
 def release_owned():
  nonlocal released
  if released:return
  released=True
  if maintenance is not None:
   for transport in maintenance.transports:transport.close()
   maintenance.store.close()
   if maintenance.new_vm is not None:maintenance.new_vm.close()
  if vm is not None:
   vm["process"].close(); vm["images"].close()
  for tool in tools.values():tool.close()
  if anchor is not None:anchor.close()
  inputs.close()
 try:
  require(os.geteuid()!=0,"GROWTH_ORDINARY_COORDINATOR")
  require(history.c.VM_ADOPTION_CLOSURE is not None and history.c.RESUMED_VM_CLOSURE is not None,"GROWTH_RC_NOT_AUTHORIZED")
  sources=growth_sources(args.expected_commit)
  require(all(resource.getrlimit(key)==(resource.RLIM_INFINITY,resource.RLIM_INFINITY)
for key in (resource.RLIMIT_CPU,resource.RLIMIT_FSIZE)),"GROWTH_INHERITED_MUTATOR_LIMIT")
  require(not args.execute or args.window_binding and args.preflight,"GROWTH_ORIGINAL_WINDOW_REQUIRED")
  require(args.execute or not (args.window_binding or args.preflight),"GROWTH_PRECHECK_REPLAY")
  require(args.trusted_single_admin,"GROWTH_ACCESS_PREMISE")
  require(args.trusted_guest_startup,"GROWTH_GUEST_STARTUP_PREMISE")
  handoff=parse_preflight(args.preflight.encode("ascii")) if args.preflight else None
  usage=Usage(None if handoff is None else handoff["usage"])
  window=Window()
  bind_window(window,args.window_binding.encode("ascii") if args.window_binding else None)
  resource.setrlimit(resource.RLIMIT_AS,(256*MIB,VM_LIMITS[resource.RLIMIT_AS][1]))
  resource.setrlimit(resource.RLIMIT_NOFILE,(128,VM_LIMITS[resource.RLIMIT_NOFILE][1]))
  require(args.q1_sources is not None,"GROWTH_Q1_SOURCES_REQUIRED")
  q1_sources=prior.r.parse(args.q1_sources.encode("ascii"),65536)
  frozen=freeze_growth_inputs(inputs,args.frame,args.plan_archive,args.archives_dir,q1_sources=q1_sources)
  frozen["guest_startup_assurance"]=guest_startup_assurance()
  window.check()
  anchor=GrowthAnchor(frozen["anchor_path"],window)
  Store(anchor.fd,window.check).absent()
  anchor.growth_inputs(frozen,sources)
  require(args.vm_activation is not None,"GROWTH_VM_ACTIVATION_REQUIRED")
  activation=adopt_vm_activation(inputs,frozen,prior.r.parse(args.vm_activation.encode("ascii"),4096))
  require(args.local_preflight is not None,"GROWTH_LOCAL_PREFLIGHT_REQUIRED")
  history.adopt_local_preflight(inputs,frozen,prior.r.parse(args.local_preflight.encode("ascii"),4096))
  require(activation["schema"]=="local-hand-q2-vm-activation/v2","GROWTH_CURRENT_GUEST_REQUIRED")
  require(activation["host_boot_id"]==window.binding["boot_id"],"GROWTH_ACTIVATION_HOST_BOOT")
  for name,path in (("qemu","/usr/bin/qemu-system-x86_64"),("image","/usr/bin/qemu-img")):
   tools[name]=Tool(path,window.check)
  vm=freeze_vm(anchor.raw["start.sh"],anchor.path,anchor.fd,tools["qemu"],window.check,activation=activation)
  frozen["journal_serial"]=vm["images"].journal_serial
  maintenance=Maintenance(anchor,inputs,frozen,sources,vm,tools,window,args.expected_commit,
usage,None if handoff is None else handoff["nonce"])
  anchor.start_custody(args.expected_commit,maintenance.nonce,sources,frozen)
  require(args.transport_failure is not None,"GROWTH_TRANSPORT_FAILURE_REQUIRED")
  history.adopt_transport_failure(inputs,frozen,prior.r.parse(args.transport_failure.encode("ascii"),4096))
  manifest=maintenance.preflight()
  sha=digest(canonical(manifest))
  if args.execute:
   require(args.expected_manifest==sha,"GROWTH_MANIFEST_NOT_FROZEN")
   require(handoff["D"]==args.expected_commit and handoff["manifest_sha256"]==sha
and handoff["window_binding"]==window.binding
and handoff["nonce"]==manifest["nonce"]
and handoff["resume_sha256"]==resume_sha256(manifest["resume"]),"GROWTH_PREFLIGHT_BINDING")
   result=maintenance.run(manifest)
  else:
   result=dict(state="LOCAL_PREFLIGHT_PASSED",D=args.expected_commit,manifest_sha256=sha,
window_binding=window.binding,
preflight=make_preflight(args.expected_commit,sha,window.binding,maintenance.nonce,usage.sample(),resume=manifest["resume"]),
kernel_report=window.kernel_report,
manifest=manifest,ssh_requests=0,marker_created=False,business_cases=0)
  receipt_sha=digest(canonical(result))
  release_owned()
  final_usage=usage.sample()
  if not args.execute:result["preflight"]["usage"]=final_usage
  else:result["coordinator_completion"]=dict(returncode=0 if result["state"]=="VERIFIED" else 3,receipt_sha256=receipt_sha,
child=anchor.custody_exit,usage=final_usage)
  print(canonical(result).decode("ascii"),end="")
  return 0 if result["state"] in ("LOCAL_PREFLIGHT_PASSED","VERIFIED") else 3
 except (Exception,KeyboardInterrupt) as error:
  marked=maintenance is not None and (maintenance.result.get("marker_created",False) or "consumed.json" in maintenance.store.opened)
  print(canonical(dict(state="UNKNOWN" if marked else "BLOCKED",reason=prior.safe_reason(error),
error_type=type(error).__name__,errno=getattr(error,"errno",None),marker_created=marked,
diagnostic=getattr(error,"diagnostic",{}),
management_usage=None if usage is None else usage.last,
window_binding=getattr(window,"binding",dict(origins=window.origins) if window else None),
ssh_requests=maintenance.result["ssh_requests"] if maintenance else 0)).decode(),end="")
  return 3
 finally:
  release_owned()
  for key,limits in VM_LIMITS.items():resource.setrlimit(key,limits)
if __name__=="__main__":
 sys.exit(main())
