"""Journal helpers."""
import hashlib
import fcntl
import os
import stat
import base64
import json
import re
import resource
import select
import selectors
import shlex
import struct
import subprocess
import sys
import time
import pwd
from e3_host import q2_core_capacity_reader as r
require, canonical, digest=r.require, r.canonical, r.digest
MAX_BYTES, MAX_ENTRIES=268435456, 32768
SESSION="lhqjgrow-20261010d"
SCHEMA="lhq-journal-growth-input/v5"
RETAINED_QUOTA_SHA="b782a2de862b038347d8b224ed55c3e9dff06179f901b06a2506fa542a0357d5"
REPORT_SCHEMA="lhq-journal-growth-guest/v4"
OLD_SIZE, NEW_SIZE=268435456, 536870912
STREAM_LIMIT=1048576
ENVIRONMENT={"HOME": "/root", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
 "LANG": "C", "LC_ALL": "C", "SYSTEMD_COLORS": "0",
 "SYSTEMD_PAGER": "cat"}
UNIT_PATTERN=re.compile(r"[A-Za-z0-9_.:@\\x-]{1,240}\.(?:service|scope|slice|socket|timer|path|target)")
RUNTIME_BINDING_SHA="8593dcfdf2b169176b8f7025e392a9942589ee19d3cc9d3c04a5692a5f6ccd9b"
RUNTIME_SOURCES={
 "original_plan":"efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c",
 "retry_preparation":"586f0fd79ceb869a8e1ed238d925b6cdbf2cceaddf233687df81ea320bded4fb",
 "system_plan":"85633b837718282ba6590b7a6679d51aa60addfb0f5be39ea929af83de4a45c1",
 "q2_prepare.py":"763ac7a7fcfb59f534f5752767cb7b84791cd5538b693fed232248d24da1904b",
 "q2_prepare_contract.py":"dd2e459798edcfa73742ffea453dd54b81cfaa07cdac9700adf46752ab0af0c5"}
RUNTIME_ROLES=("controller","management","supervisor","query","ordinary","retained_ordinary")
def validate_runtime_binding(value, inventory=None):
 require(type(value) is dict and set(value)=={"schema","sources","account","parents","manager"}
 and len(canonical(value))<=8192 and digest(canonical(value))==RUNTIME_BINDING_SHA
 and value["schema"]=="lhq-runtime-parent-binding/v1" and value["sources"]==RUNTIME_SOURCES,
 "GROWTH_RUNTIME_BINDING")
 require(type(value["account"]) is dict and set(value["account"])=={"name","uid","gid"}
 and value["account"]["uid"]==value["account"]["gid"]==1100
 and re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}",value["account"]["name"]),"GROWTH_RUNTIME_ACCOUNT")
 require(type(value["parents"]) is dict and set(value["parents"])==set(RUNTIME_ROLES),"GROWTH_RUNTIME_ROLES")
 for role,row in value["parents"].items():
  require(type(row) is dict and set(row)=={"unit","manager","control_group","memory_bytes","tasks_max","cpu_quota_per_sec_usec"}
 and UNIT_PATTERN.fullmatch(row["unit"]) and row["unit"].endswith(".slice")
 and row["manager"]==("user" if role=="retained_ordinary" else "system")
 and row["memory_bytes"]==(268435456 if role in ("ordinary","retained_ordinary","query") else 536870912)
 and row["tasks_max"]==(32 if role=="ordinary" else 64)
 and row["cpu_quota_per_sec_usec"]==1000000,"GROWTH_RUNTIME_ROLE")
  r.path_value(row["control_group"])
  if inventory is not None:
   require(dict(name=row["unit"],manager=row["manager"],control_group=row["control_group"])
 in inventory["domain_units"] and row["control_group"] in inventory["domain_cgroups"],"GROWTH_RUNTIME_DOMAIN")
 manager=value["manager"]
 require(type(manager) is dict and set(manager)=={"unit","control_group","fragment","dropins"}
 and manager["unit"]=="user@1100.service" and manager["control_group"]=="/user.slice/user-1100.slice/user@1100.service"
 and manager["fragment"]=="/usr/lib/systemd/system/user@.service"
 and type(manager["dropins"]) is list and 1<=len(manager["dropins"])<=8,"GROWTH_RUNTIME_MANAGER")
 for path in manager["dropins"]:r.path_value(path)
 require(value["parents"]["ordinary"]["control_group"]=="/"+value["parents"]["controller"]["unit"]+"/"+value["parents"]["ordinary"]["unit"]
 and value["parents"]["retained_ordinary"]["control_group"]==manager["control_group"]+"/"+value["parents"]["retained_ordinary"]["unit"],"GROWTH_RUNTIME_HIERARCHY")
 return value
def runtime_config(row, *, manager=False):
 prefix=("[Service]\nDelegate=cpu memory pids\n" if manager else
 "[Unit]\nDescription=Local Hand isolated Q2 preparation\nStopWhenUnneeded=no\n[Slice]\n")
 require(row["cpu_quota_per_sec_usec"]==1000000,"GROWTH_RUNTIME_CPU")
 return (prefix+"CPUAccounting=yes\nCPUQuota=100%\nCPUQuotaPeriodSec=100ms\nMemoryAccounting=yes\nMemoryMax="
 +str(row["memory_bytes"])+"\nMemorySwapMax=0\nTasksAccounting=yes\nTasksMax="+str(row["tasks_max"])+"\n").encode()
def guest_startup_assurance():
 """Fixed Owner-confirmed management premise, not an observation result."""
 return dict(mode="TRUSTED_SINGLE_ADMIN", indirect_startup_observation="NOT_PERFORMED",
 undeclared_unit_inventory_observation="NOT_PERFORMED",
 no_undeclared_business_startup=True, continuous_exclusion_proven=False)
def validate_startup_assurance(value):
 require(type(value) is dict and canonical(value)==canonical(guest_startup_assurance()),
 "GROWTH_GUEST_STARTUP_PREMISE")
 return value
def validate_startup_report(value, description):
 validate_startup_assurance(description.get("guest_startup_assurance"))
 expected={"system"}
 if any(row["manager"]=="user" for row in description["domain_units"]):expected.add("user_1100")
 require(type(value) is dict and set(value)==expected, "GROWTH_STARTUP_MANAGERS")
 for manager,row in value.items():
  require(type(row) is dict and set(row)=={"scope","domains","undeclared_unit_inventory","indirect_startup"}
 and row["scope"]=="DECLARED_ONLY" and row["undeclared_unit_inventory"]=="NOT_PERFORMED"
 and row["indirect_startup"]=="NOT_PERFORMED" and type(row["domains"]) is list,
 "GROWTH_STARTUP_COVERAGE")
  names=sorted(item["name"] for item in description["domain_units"]
 if item["manager"]==("system" if manager=="system" else "user"))
  require(len(row["domains"])==len(names),"GROWTH_STARTUP_DOMAINS")
  for item,name in zip(row["domains"],names):
   require(type(item) is dict and set(item)=={"name","properties_sha256"}
 and type(item["name"]) is str and item["name"]==name
 and type(item["properties_sha256"]) is str
 and re.fullmatch(r"[0-9a-f]{64}",item["properties_sha256"]),"GROWTH_STARTUP_DOMAINS")
 return value
def control_limits():
 for key,value in ((resource.RLIMIT_AS,268435456),(resource.RLIMIT_NOFILE,128),(resource.RLIMIT_CORE,0)):
  resource.setrlimit(key,(value,value))
def identity(info):
 return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink)
def stable_identity(info):
 return identity(info) + (info.st_size, info.st_mtime_ns, info.st_ctime_ns)
def validate_file(info, cap, owner):
 require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == owner
 and stat.S_IMODE(info.st_mode) == 0o600 and 0 <= info.st_size <= cap
 and info.st_blocks * 512 <= cap, "GROWTH_FILE")
def write_all(fd, raw, check):
 view=memoryview(raw)
 while view:
  check()
  count=os.write(fd, view)
  require(count > 0, "GROWTH_SHORT_WRITE")
  view=view[count:]
 check()
def hash_fd(fd, cap, check):
 before=os.fstat(fd)
 require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
 "GROWTH_HASH_FILE")
 os.lseek(fd, 0, os.SEEK_SET)
 value, count=hashlib.sha256(), 0
 while True:
  check()
  part=os.read(fd, min(65536, cap + 1 - count))
  check()
  if not part:
   break
  count += len(part)
  require(count <= cap, "GROWTH_HASH_LIMIT")
  value.update(part)
 require(count == before.st_size and stable_identity(os.fstat(fd)) == stable_identity(before),
 "GROWTH_HASH_DRIFT")
 return dict(bytes=count, sha256=value.hexdigest())
def proc_start(raw):
 tail=raw.rpartition(b") ")[2].split()
 require(len(tail) >= 20 and tail[19].isdigit(), "GROWTH_PROC_STAT")
 return int(tail[19])
def proc_bytes(pid, name, cap, check):
 require(type(pid) is int and pid > 0 and name in ("stat", "cmdline", "status"), "GROWTH_PROC_PATH")
 path=f"/proc/{pid}/{name}"
 check()
 fd=os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC)
 try:
  require(r.filesystem_type(fd) == 0x9FA0, "GROWTH_PROCFS")
  raw=os.read(fd, cap + 1)
  require(len(raw) <= cap and identity(os.fstat(fd)) == identity(os.stat(path, follow_symlinks=False)),
 "GROWTH_PROC_DRIFT")
  check()
  return raw
 finally:
  os.close(fd)
def growth_descriptor(frozen, nonce, phase, window, pre=None):
 value=dict(schema=SCHEMA, session=SESSION, phase=phase, nonce=nonce,
 runtime_parent_binding=validate_runtime_binding(frozen["runtime_parent_binding"],frozen["inventory"]),
 guest_startup_assurance=validate_startup_assurance(frozen.get("guest_startup_assurance")),
 source_binding_sha256=frozen["source_binding_sha256"], paths=frozen["paths"],
 saved_rows=frozen["saved_rows"], original_boot_id=frozen["boot_id"],
 journal_serial=frozen["journal_serial"], **frozen["inventory"],
 window_seconds=int(window.remaining()), change_seconds=int(window.remaining(780)))
 if pre is not None:
  value.update(pre_report=pre, pre_report_sha256=digest(canonical(pre)))
 descriptor(canonical(value))
 return value
def bind_window(window, raw=None):
 value=r.parse(raw, 256) if raw is not None else None
 if value is not None:
  require(type(value) is dict and set(value) == {"boot_id", "origins"}
 and type(value["origins"]) is list and len(value["origins"]) == 2, "GROWTH_WINDOW_BINDING")
  uuid_value(value["boot_id"])
  for origin in value["origins"]: r.integer(origin)
  window.origins=window.previous=tuple(value["origins"])
 window.check()
 window.kernel_report={}
 window.binding=dict(boot_id=host_boot_id(window.check, window.kernel_report), origins=list(window.origins))
 require(value is None or value == window.binding, "GROWTH_HOST_BOOT_CHANGED")
 return window.binding
def host_boot_id(check, report=None):
 from e3_host import q2_host_kernel_facts as kernel
 report={} if report is None else report
 try:
  raw=kernel.read_fact("boot", check, report)
 except kernel.KernelFactError as error:
  failure=r.ObservationError("GROWTH_HOST_KERNEL_FACT")
  failure.diagnostic=error.detail
  raise failure from error
 require(len(raw) == 37 and raw.endswith(b"\n"), "GROWTH_BOOT")
 return uuid_value(raw[:-1].decode("ascii"))
def sha_value(value):
 require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "GROWTH_SHA")
 return value
def uuid_value(value):
 require(type(value) is str and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value)
 and value != "00000000-0000-0000-0000-000000000000", "GROWTH_UUID")
 return value
def resource_observation():
 self_use=resource.getrusage(resource.RUSAGE_SELF)
 children=resource.getrusage(resource.RUSAGE_CHILDREN)
 return dict(self_cpu_microseconds=int((self_use.ru_utime + self_use.ru_stime) * 1000000),
 exited_children_cpu_microseconds=int((children.ru_utime + children.ru_stime) * 1000000),
 self_peak_rss_bytes=self_use.ru_maxrss * 1024,
 exited_child_peak_rss_bytes=children.ru_maxrss * 1024,
 coverage="THROUGH_REPORT_ONLY", complete=False)
def retained_quota_roots(value):
 roots=value["retained_quota_roots"]
 require(type(roots) is list and len(roots)==4 and digest(canonical(roots))==RETAINED_QUOTA_SHA,
 "GROWTH_RETAINED_ROOT_PIN")
 require(all(row["path"] in value["essential_paths"] and row["path"] in value["protected_roots"]
 for row in roots),"GROWTH_RETAINED_ROOT_COVERAGE")
 return {row["path"]:row for row in roots}
def retained_sample(report,description):
 value=report["quiescence"]["persistent"]["retained_roots"]
 require(type(value) is dict and set(value)=={"count","sha256"} and type(value["count"]) is int
 and value["count"]==len(retained_quota_roots(description)),"GROWTH_RETAINED_SAMPLE")
 sha_value(value["sha256"])
 return value
def descriptor(raw):
 value=r.parse(raw, 65536)
 keys={"schema", "session", "phase", "nonce", "source_binding_sha256", "paths", "saved_rows",
 "original_boot_id", "journal_serial", "expected_units", "domain_cgroups", "domain_units",
 "protected_roots", "essential_paths", "retained_quota_roots", "window_seconds", "change_seconds", "guest_startup_assurance", "runtime_parent_binding"}
 require(type(value) is dict and value.get("phase") in ("pre", "post"), "GROWTH_DESCRIPTION")
 if value["phase"] == "post":
  keys |= {"pre_report", "pre_report_sha256"}
 require(set(value) == keys and value["schema"] == SCHEMA and value["session"] == SESSION,
 "GROWTH_DESCRIPTION")
 retained_quota_roots(value)
 validate_startup_assurance(value.get("guest_startup_assurance"))
 validate_runtime_binding(value.get("runtime_parent_binding"),value)
 sha_value(value["nonce"]); sha_value(value["source_binding_sha256"])
 uuid_value(value["original_boot_id"])
 require(type(value["journal_serial"]) is str and
 re.fullmatch(r"[A-Za-z0-9_.-]{1,20}", value["journal_serial"]), "GROWTH_SERIAL")
 require(type(value["paths"]) is dict and set(value["paths"]) == set(r.ROLES), "GROWTH_PATHS")
 for path in value["paths"].values():
  r.path_value(path)
 require(type(value["saved_rows"]) is list and len(value["saved_rows"]) == 5,
 "GROWTH_SAVED_ROWS")
 for role, row in zip(r.ROLES, value["saved_rows"]):
  require(type(row) is dict and row.get("role") == role and row.get("path") == value["paths"][role],
 "GROWTH_SAVED_ROW")
  uuid_value(row["filesystem"]["uuid"])
 for key in ("domain_cgroups", "protected_roots", "essential_paths"):
  paths=value[key]
  require(type(paths) is list and 0 < len(paths) <= 512 and paths == sorted(set(paths)),
 "GROWTH_INVENTORY_PATHS")
  for path in paths:
   r.path_value(path)
 for key in ("expected_units", "domain_units"):
  rows=value[key]
  require(type(rows) is list and 0 < len(rows) <= 256, "GROWTH_INVENTORY_UNITS")
  seen=set()
  for row in rows:
   fields={"name", "control_group"} | ({"manager"} if key == "domain_units" else set())
   require(type(row) is dict and set(row) == fields and type(row["name"]) is str
 and UNIT_PATTERN.fullmatch(row["name"]) and row["name"] not in seen,
 "GROWTH_UNIT_DESCRIPTION")
   seen.add(row["name"])
   if row["control_group"] is not None:
    r.path_value(row["control_group"])
   if key == "domain_units":
    require(row["manager"] in ("system", "user") and row["control_group"] in value["domain_cgroups"],
 "GROWTH_DOMAIN_DESCRIPTION")
 r.integer(value["window_seconds"], 1, 900)
 r.integer(value["change_seconds"], 1, min(780, value["window_seconds"]))
 if value["phase"] == "post":
  sha_value(value["pre_report_sha256"])
  require(digest(canonical(value["pre_report"])) == value["pre_report_sha256"], "GROWTH_PRE_REPORT_DIGEST")
  validate_pre_report(value["pre_report"], value)
 return value
class GuestWindow:
 """Observation bounds only; never raises a timer signal into a mutator."""
 def __init__(self, seconds, change_seconds, *, clock=time.clock_gettime_ns):
  self.clock, self.seconds, self.change_seconds=clock, seconds, change_seconds
  self.start=self.previous=self.read()
  self.usage_start=resource.getrusage(resource.RUSAGE_SELF)
 def read(self):
  return (self.clock(time.CLOCK_MONOTONIC), self.clock(time.CLOCK_BOOTTIME))
 def check(self, change=False):
  now=self.read()
  limit=self.change_seconds if change else self.seconds
  require(all(p <= n < s + limit * 10**9 for p, n, s in zip(self.previous, now, self.start)),
 "GROWTH_GUEST_CHANGE_DEADLINE" if change else "GROWTH_GUEST_DEADLINE")
  self.previous=now
  usage=resource.getrusage(resource.RUSAGE_SELF)
  children=resource.getrusage(resource.RUSAGE_CHILDREN)
  cpu=usage.ru_utime + usage.ru_stime + children.ru_utime + children.ru_stime
  require(cpu <= 120 and max(usage.ru_maxrss, children.ru_maxrss) <= 512 * 1024,
 "GROWTH_GUEST_OBSERVATION_BUDGET")
def open_path(path, *, directory=False, writable=False, block=False, owners=(0,), retained=None):
 """Walk protected ancestors by fd; no symlink or weak atime fallback."""
 require(retained is None or (directory and not writable and not block and retained["path"]==path),
 "GROWTH_RETAINED_READ_ONLY")
 parts=r.path_value(path)
 current=None;index=-1;operation="open_root";qualification=None
 try:
  current=os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC)
  operation="qualify_root"
  info=os.fstat(current)
  qualification=dict(dev=info.st_dev,ino=info.st_ino,uid=info.st_uid,gid=info.st_gid,mode=info.st_mode,
 allowed_uids=[0],forbidden_write_bits=0o022)
  r.qualify(info)
  for index, name in enumerate(parts):
   qualification=None
   last=index == len(parts) - 1
   flags=(os.O_RDWR if writable and last else os.O_RDONLY) | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NOATIME | os.O_NONBLOCK
   if not last or directory:
    flags |= os.O_DIRECTORY
   operation="open_component"
   next_fd=os.open(name, flags, dir_fd=current)
   os.close(current)
   current=next_fd
   operation="qualify_component"
   info=os.fstat(current)
   qualification=dict(dev=info.st_dev,ino=info.st_ino,uid=info.st_uid,gid=info.st_gid,mode=info.st_mode,
 allowed_uids=list(owners),forbidden_write_bits=0o002 if last and block else 0o022)
   if not last:
    require(stat.S_ISDIR(info.st_mode) and info.st_uid in owners and not info.st_mode & 0o022,
 "GROWTH_PATH_ANCESTOR")
   else:
    if retained is not None:
     qualification.update(allowed_uids=None,retained_root={k:retained[k] for k in ("device","inode")})
     require(stat.S_ISDIR(info.st_mode) and (info.st_dev,info.st_ino)==(retained["device"],retained["inode"]),
 "GROWTH_RETAINED_ROOT_IDENTITY")
    require((retained is not None or info.st_uid in owners) and not info.st_mode & (0o002 if block else 0o022), "GROWTH_PATH_PROTECTION")
    if block:
     require(stat.S_ISBLK(info.st_mode), "GROWTH_BLOCK_TYPE")
  result, current=(current,r.identity(info)) if retained is not None else current, None
  return result
 except (OSError,r.ObservationError) as error:
  # Identify the already attempted lookup, without another read or raw path.
  error.path_diagnostic=dict(operation=operation,path_bytes=len(path),
 path_sha256=digest(path.encode("ascii")),component_index=index)
  if qualification is not None:
   error.path_diagnostic["qualification"]=qualification
  raise
 finally:
  if current is not None:
   os.close(current)
def read_fd(fd, cap, check):
 raw=bytearray()
 while True:
  check()
  part=os.read(fd, min(65536, cap + 1 - len(raw)))
  if not part:
   return bytes(raw)
  raw.extend(part)
  require(len(raw) <= cap, "GROWTH_READ_LIMIT")
def read_kernel(path, cap, check, *, expected_fs):
 check()
 try:
  fd=os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC | os.O_NONBLOCK)
 except OSError as error:
  failure=r.ObservationError("GROWTH_KERNEL_OPEN")
  failure.diagnostic=dict(operation="open_kernel", target="boot" if
 path == "/proc/sys/kernel/random/boot_id" else "kernel_view", errno=error.errno)
  raise failure from error
 try:
  info=os.fstat(fd)
  require(stat.S_ISREG(info.st_mode) and r.filesystem_type(fd) == expected_fs, "GROWTH_KERNEL_SOURCE")
  raw=read_fd(fd, cap, check)
  require(r.identity(info) == r.identity(os.fstat(fd)), "GROWTH_KERNEL_DRIFT")
  return raw
 finally:
  os.close(fd)
def boot_id(check):
 raw=read_kernel("/proc/sys/kernel/random/boot_id", 64, check, expected_fs=0x9FA0)
 require(len(raw) == 37 and raw.endswith(b"\n"), "GROWTH_BOOT")
 return uuid_value(raw[:-1].decode("ascii"))
class GuestCommand:
 """Bounded pipes, natural exit only; an overdue process remains UNKNOWN."""
 def __init__(self, argv, check, *, limit=STREAM_LIMIT, pass_fds=(), executable=None,
 environment=None, preexec_fn=None):
  self.check, self.limit=check, limit
  self.check()
  self.process=subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
 stderr=subprocess.PIPE, env=environment or ENVIRONMENT, close_fds=True,
 pass_fds=pass_fds, executable=executable, preexec_fn=preexec_fn)
  self.output={"stdout": bytearray(), "stderr": bytearray()}
  self.eof={"stdout": False, "stderr": False}
  self.closed=False
 def collect(self):
  selector=selectors.DefaultSelector()
  try:
   for name in self.output:
    stream=getattr(self.process, name)
    os.set_blocking(stream.fileno(), False)
    selector.register(stream, selectors.EVENT_READ, name)
   while selector.get_map() or self.process.poll() is None:
    self.check()
    for key, _ in selector.select(0.05):
     name=key.data
     try:
      part=os.read(key.fileobj.fileno(), min(65536, self.limit + 1 - len(self.output[name])))
     except BlockingIOError:
      continue
     if not part:
      self.eof[name]=True
      selector.unregister(key.fileobj)
     else:
      self.output[name].extend(part)
      require(len(self.output[name]) <= self.limit, "GROWTH_TOOL_OUTPUT")
    self.check()
   return dict(returncode=self.process.returncode, stdout=bytes(self.output["stdout"]),
 stderr=bytes(self.output["stderr"]), both_eof=all(self.eof.values()), pid=self.process.pid)
  finally:
   selector.close()
   self.close()
 def close(self):
  if not self.closed:
   self.closed=True
   self.process.stdout.close(); self.process.stderr.close()
def run_command(argv, check, *, codes=(0,), limit=STREAM_LIMIT):
 command=GuestCommand(argv, check, limit=limit)
 result=command.collect()
 require(result["returncode"] in codes and result["both_eof"], "GROWTH_GUEST_TOOL_FAILED")
 return result
def tool_binding(path, check, *, version=False):
 fd=open_path(path)
 try:
  info=os.fstat(fd)
  require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_mode & 0o111,
 "GROWTH_TOOL_FILE")
  before=metadata(info)
  sha, count=file_hash(fd, 16 * 1048576, check)
  require(metadata(os.stat(path, follow_symlinks=False)) == before, "GROWTH_TOOL_NAME")
  result=dict(path=path, identity={k: before[k] for k in ("dev", "ino", "mode", "uid", "gid", "nlink")},
 bytes=count, sha256=sha)
  if version:
   observed=run_command([path, "-V"], check, codes=(0, 1), limit=8192)
   text=observed["stderr"] + observed["stdout"]
   require(re.match(rb"resize2fs [0-9][^\r\n]{0,128}\n", text), "GROWTH_RESIZE_VERSION")
   result["version_sha256"]=digest(text)
   require(metadata(os.stat(path, follow_symlinks=False)) == before and metadata(os.fstat(fd)) == before,
 "GROWTH_TOOL_DRIFT")
  return result
 finally:
  os.close(fd)
def verify_tool(binding, check):
 observed=tool_binding(binding["path"], check, version="version_sha256" in binding)
 require(observed == binding, "GROWTH_TOOL_CHANGED")
def bound_command(binding, arguments, check, *, limit=STREAM_LIMIT, environment=None, preexec_fn=None):
 """Execute the held, byte-checked inode rather than a racy pathname."""
 fd=open_path(binding["path"])
 try:
  before=metadata(os.fstat(fd))
  require({key: before[key] for key in binding["identity"]} == binding["identity"], "GROWTH_TOOL_CHANGED")
  sha, count=file_hash(fd, 16 * 1048576, check)
  require((sha, count) == (binding["sha256"], binding["bytes"]), "GROWTH_TOOL_CHANGED")
  command=GuestCommand([binding["path"], *arguments], check, limit=limit, pass_fds=(fd,),
 executable="/proc/self/fd/" + str(fd), environment=environment, preexec_fn=preexec_fn)
  return command
 finally:
  os.close(fd)
def same_parents(before_rows, after_rows):
 require(len(before_rows) == len(after_rows) == 5, "GROWTH_PARENT_COUNT")
 for before, after in zip(before_rows, after_rows):
  require(before["role"] == after["role"] and before["path"] == after["path"]
 and before["filesystem"]["uuid"] == after["filesystem"]["uuid"], "GROWTH_PARENT_IDENTITY")
  for key in ("ino", "mode", "uid", "gid"):
   require(before["directory"][key] == after["directory"][key], "GROWTH_PARENT_DIRECTORY")
  for key in ("root", "path", "fstype", "options"):
   require(before["filesystem"]["mount"][key] == after["filesystem"]["mount"][key], "GROWTH_PARENT_MOUNT")
class JournalDevice:
 def __init__(self, row, serial, expected_size, check):
  self.row, self.check=row, check
  mount=row["filesystem"]["mount"]
  require(row["role"] == "journal" and mount["root"] == "/" and mount["fstype"] == "ext4"
 and mount["path"] == row["path"] and "rw" in mount["options"] and "ro" not in mount["options"],
 "GROWTH_JOURNAL_MOUNT")
  self.path=mount["source"]
  require(re.fullmatch(r"/dev/vd[a-z]+", self.path), "GROWTH_JOURNAL_DEVICE_NAME")
  self.fd=open_path(self.path, block=True)
  try:
   self.info=metadata(os.fstat(self.fd))
   self.rdev=os.fstat(self.fd).st_rdev
   require(self.rdev == mount["device"] == row["directory"]["dev"], "GROWTH_JOURNAL_DEVICE_BINDING")
   self.syslink="/sys/dev/block/" + str(os.major(self.rdev)) + ":" + str(os.minor(self.rdev))
   target=os.readlink(self.syslink)
   self.syspath=os.path.realpath(self.syslink)
   require(target.startswith("../../devices/") and self.syspath.startswith("/sys/devices/")
 and self.syspath.endswith("/block/" + self.path.rsplit("/", 1)[1])
 and "/virtio" in self.syspath, "GROWTH_JOURNAL_SYSFS")
   self.syslink_target=target
   try:
    os.stat(self.syspath + "/partition", follow_symlinks=False)
   except FileNotFoundError:
    pass
   else:
    raise r.ObservationError("GROWTH_JOURNAL_PARTITION")
   observed_serial=read_kernel(self.syspath + "/serial", 128, check, expected_fs=0x62656572)
   # Linux virtio_blk serial_show returns the ID bytes without a newline.
   # Compare the complete ID; never normalize whitespace or accept a prefix.
   expected_serial=serial.encode("ascii")
   if observed_serial != expected_serial:
    failure=r.ObservationError("GROWTH_JOURNAL_SERIAL")
    failure.serial_diagnostic=dict(expected_bytes=len(expected_serial),actual_bytes=len(observed_serial),
 expected_hex=expected_serial.hex(),actual_hex=observed_serial.hex())
    raise failure
   size=bytearray(8)
   fcntl.ioctl(self.fd, 0x80081272, size, True)
   self.size=struct.unpack("=Q", size)[0]
   sector_count=read_kernel(self.syspath + "/size", 64, check, expected_fs=0x62656572)
   require(re.fullmatch(rb"[0-9]+\n", sector_count) and int(sector_count) * 512 == self.size == expected_size,
 "GROWTH_JOURNAL_BLOCK_SIZE")
   self.serial=serial
   self.superblock=self.read_superblock()
   require(self.superblock["uuid"] == row["filesystem"]["uuid"] and
 self.superblock["filesystem_bytes"] <= expected_size, "GROWTH_EXT4_BINDING")
   self.recheck()
  except BaseException:
   os.close(self.fd)
   self.fd=None
   raise
 def report(self):
  return dict(path=self.path, uuid=self.row["filesystem"]["uuid"], serial=self.serial,
 block_bytes=self.size, node={k: self.info[k] for k in ("mode", "uid", "gid")},
 superblock=self.superblock)
 def read_superblock(self):
  self.check()
  raw=os.pread(self.fd, 1024, 1024)
  require(len(raw) == 1024 and raw[56:58] == b"\x53\xef", "GROWTH_EXT4_SUPERBLOCK")
  log_size=struct.unpack_from("<I", raw, 24)[0]
  require(log_size <= 6, "GROWTH_EXT4_BLOCKSIZE")
  features=list(struct.unpack_from("<III", raw, 92))
  blocks=struct.unpack_from("<I", raw, 4)[0]
  if features[1] & 0x80:
   blocks |= struct.unpack_from("<I", raw, 336)[0] << 32
  import uuid
  return dict(uuid=str(uuid.UUID(bytes=raw[104:120])), features=features,
 block_size=1024 << log_size, filesystem_bytes=blocks * (1024 << log_size))
 def recheck(self):
  self.check()
  require(metadata(os.fstat(self.fd)) == self.info and
 metadata(os.stat(self.path, follow_symlinks=False)) == self.info
 and os.stat(self.path, follow_symlinks=False).st_rdev == self.rdev,
 "GROWTH_JOURNAL_DEVICE_DRIFT")
  require(os.readlink(self.syslink) == self.syslink_target and os.path.realpath(self.syslink) == self.syspath,
 "GROWTH_JOURNAL_SYSFS_DRIFT")
 def close(self):
  if self.fd is not None:
   os.close(self.fd)
   self.fd=None
def under(path, roots):
 return any(path == root or path.startswith(root.rstrip("/") + "/") for root in roots)
def process_start(raw):
 require(type(raw) is bytes and b") " in raw, "GROWTH_PROCESS_STAT")
 fields=raw.rsplit(b") ", 1)[1].split()
 require(len(fields) >= 20 and fields[19].isdigit(), "GROWTH_PROCESS_STAT")
 return int(fields[19])
class GuestInventory:
 EXEC_PROPERTIES=frozenset(("ExecStart", "ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost", "ExecReload"))
 SHOW=("Id", "Names", "LoadState", "ActiveState", "SubState", "MainPID", "ControlPID", "ControlGroup",
 "Restart", "UnitFileState", "Triggers", "TriggeredBy", "WantedBy", "RequiredBy",
 "UpheldBy", "OnSuccess", "OnFailure", "Job", "Transient", "FragmentPath", "DropInPaths",
 "ExecStart", "ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost", "ExecReload",
 "WorkingDirectory", "RootDirectory", "RootImage")
 def __init__(self, description, check):
  self.description, self.check=description, check
  self.roots=description["protected_roots"]
  self.systemctl=tool_binding("/usr/bin/systemctl", check)
  self.records=[]
  self.context={}
  self.command_count=0
 def ctl(self, arguments, *, user_uid=None, runtime_missing=False):
  self.last_result=None
  self.command_count += 1
  self.context=dict(manager="user_1100" if user_uid is not None else "system",
 command_index=self.command_count, verb=arguments[0], arguments_sha256=digest(canonical(arguments)),
 unit_count=sum(UNIT_PATTERN.fullmatch(value) is not None for value in arguments))
  environment, child_setup=None, None
  bus=None
  if user_uid is not None:
   require(user_uid == 1100, "GROWTH_USER_MANAGER_UID")
   account=pwd.getpwuid(1100)
   require(account.pw_uid == account.pw_gid == 1100, "GROWTH_USER_MANAGER_ACCOUNT")
   runtime_fd=open_path("/run/user/1100", directory=True, owners=(0, 1100))
   try:
    info=os.fstat(runtime_fd)
    require(info.st_uid == info.st_gid == 1100 and stat.S_IMODE(info.st_mode) == 0o700,
 "GROWTH_USER_RUNTIME")
    bus=os.stat("bus", dir_fd=runtime_fd, follow_symlinks=False)
    require(stat.S_ISSOCK(bus.st_mode) and bus.st_uid == bus.st_gid == 1100,
 "GROWTH_USER_BUS")
    bus=r.identity(bus)
   finally:
    os.close(runtime_fd)
   environment=dict(ENVIRONMENT, XDG_RUNTIME_DIR="/run/user/1100",
 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1100/bus")
   def child_setup():
    os.setgroups([])
    os.setresgid(1100, 1100, 1100)
    os.setresuid(1100, 1100, 1100)
  command=bound_command(self.systemctl, ["--user" if user_uid else "--system", "--no-pager",
 "--no-ask-password", *arguments], self.check,
 environment=environment, preexec_fn=child_setup)
  result=command.collect()
  self.last_result={key:result[key] for key in ("returncode","both_eof")}
  for stream in ("stdout","stderr"):
   self.last_result.update({stream+"_bytes":len(result[stream]),stream+"_sha256":digest(result[stream])})
  if result["returncode"] not in ((0,1) if runtime_missing and arguments[0]=="show" else (0,)) or not result["both_eof"] or result["stderr"]:
   self.context.update(returncode=result["returncode"], both_eof=result["both_eof"], pid=result["pid"],
 stdout_bytes=len(result["stdout"]), stderr_bytes=len(result["stderr"]),
 stdout_sha256=digest(result["stdout"]), stderr_sha256=digest(result["stderr"]),
 stderr_prefix_hex=result["stderr"][:512].hex(), stderr_truncated=len(result["stderr"])>512,
 failed_checks=[name for name,failed in (("returncode",result["returncode"] != 0),
 ("both_eof",not result["both_eof"]),("stderr",bool(result["stderr"]))) if failed])
   raise r.ObservationError("GROWTH_SYSTEMCTL_STDERR")
  if bus is not None:
   require(r.identity(os.stat("/run/user/1100/bus", follow_symlinks=False)) == bus,
 "GROWTH_USER_BUS_DRIFT")
  verify_tool(self.systemctl, self.check)
  return result["stdout"]
 def show_many(self, names, *, user_uid=None, raw=None):
  require(0 < len(names) <= 128 and len(names) == len(set(names)) and
 all(type(name) is str and UNIT_PATTERN.fullmatch(name) for name in names), "GROWTH_UNIT_NAME")
  if raw is None:raw=self.ctl(["show", "--all", "--property=" + ",".join(self.SHOW), "--", *names], user_uid=user_uid)
  result, identities={}, {}
  blocks=raw.decode("utf-8", "strict").strip().split("\n\n")
  require(0 < len(blocks) <= len(names), "GROWTH_SYSTEMCTL_UNIT_SET")
  for response_index, block in enumerate(blocks, 1):
   entries, first_lines={}, {}
   for line_index, line in enumerate(block.splitlines(), 1):
    key, separator, item=line.partition("=")
    failed_check=("missing_equals" if not separator else
 "duplicate_scalar" if key in entries and key not in self.EXEC_PROPERTIES else None)
    if failed_check is not None:
     line_raw=line.encode("utf-8")
     self.context.update(response_index=response_index,
 format_diagnostic=dict(failed_check=failed_check, line_index=line_index,
 property=key if separator and key in self.SHOW else None,
 first_line_index=first_lines.get(key), line_bytes=len(line_raw), line_sha256=digest(line_raw)))
     if "Id" in entries and UNIT_PATTERN.fullmatch(entries["Id"][0]):
      self.context["unit"]=entries["Id"][0]
     raise r.ObservationError("GROWTH_SYSTEMCTL_FORMAT")
    first_lines.setdefault(key, line_index)
    entries.setdefault(key, []).append(item)
   # systemctl emits each Exec array member as a separate property line.
   # Retain every member and its order; scalar properties must remain unique.
   value={key: "\n".join(items) for key, items in entries.items()}
   require(set(value) <= set(self.SHOW) and {"Id", "LoadState", "ActiveState", "SubState"} <= set(value)
 and UNIT_PATTERN.fullmatch(value["Id"]), "GROWTH_SYSTEMCTL_FIELDS")
   names_text=value.get("Names", "")
   failed_checks=[]
   try:
    # systemctl quotes string-array elements; Id is a scalar and stays literal.
    # Decode only that display layer, never the unit name's literal \\xNN escapes.
    aliases=shlex.split(names_text, comments=False, posix=True)
   except ValueError:
    aliases=None
    failed_checks.append("parse")
   if aliases is not None:
    if len(aliases) != len(set(aliases)): failed_checks.append("duplicate")
    if not all(UNIT_PATTERN.fullmatch(name) for name in aliases): failed_checks.append("format")
    if aliases and value["Id"] not in aliases: failed_checks.append("id_member")
    if "format" not in failed_checks:
     encoded=" ".join('"' + name.replace("\\", "\\\\") + '"' if "\\" in name else name for name in aliases)
     if encoded != names_text: failed_checks.append("encoding")
   if failed_checks:
    names_raw=names_text.encode("utf-8")
    self.context.update(unit=value["Id"], response_index=response_index,
 names_diagnostic=dict(failed_checks=failed_checks,
 alias_count=None if aliases is None else len(aliases), bytes=len(names_raw),
 sha256=digest(names_raw), prefix_hex=names_raw[:512].hex(), truncated=len(names_raw)>512))
    raise r.ObservationError("GROWTH_SYSTEMCTL_NAMES")
   covered=set(names) & ({value["Id"]} | set(aliases))
   require(covered, "GROWTH_SYSTEMCTL_UNIT_SET")
   if value["Id"].endswith(".service") and value["LoadState"] == "loaded":
    require({"MainPID", "ControlPID", "Restart"} <= set(value), "GROWTH_SERVICE_FIELDS")
   value={key: value.get(key, "") for key in self.SHOW}
   require(value["Id"] not in identities or identities[value["Id"]] == value,
 "GROWTH_SYSTEMCTL_ALIAS_CONFLICT")
   identities[value["Id"]]=value
   for name in covered:
    require(name not in result or result[name] == value, "GROWTH_SYSTEMCTL_ALIAS_CONFLICT")
    result[name]=value
  require(set(result) == set(names), "GROWTH_SYSTEMCTL_UNIT_SET")
  return result
 def show(self, name):
  return self.show_many([name])[name]
 def cgroup(self, logical):
  r.path_value(logical)
  path="/sys/fs/cgroup" + logical
  try:
   fd=open_path(path, directory=True, owners=(0, 1100))
  except FileNotFoundError:
   return dict(path=logical, state="ABSENT")
  try:
   require(r.filesystem_type(fd) == 0x63677270, "GROWTH_CGROUP_FS")
   before=r.identity(os.fstat(fd))
   raw=read_kernel(path + "/cgroup.events", 512, self.check, expected_fs=0x63677270)
   fields=[line.split() for line in raw.decode("ascii").splitlines()]
   require(all(len(row) == 2 for row in fields) and len(fields) == len({row[0] for row in fields}),
 "GROWTH_CGROUP_EVENTS")
   require(dict(fields).get("populated") == "0", "GROWTH_CGROUP_POPULATED")
   procs=read_kernel(path + "/cgroup.procs", 65536, self.check, expected_fs=0x63677270)
   require(procs == b"", "GROWTH_CGROUP_PROCESSES")
   require(r.identity(os.stat(path, follow_symlinks=False)) == before == r.identity(os.fstat(fd)),
 "GROWTH_CGROUP_DRIFT")
   return dict(path=logical, state="UNPOPULATED", identity=before, events_sha256=digest(raw))
  finally:
   os.close(fd)
 def quiet_service(self, expected, value=None):
  if value is None:value=self.show(expected["name"])
  require(value["Id"] == expected["name"], "GROWTH_UNIT_IDENTITY")
  if value["LoadState"] == "not-found":
   require(value["ActiveState"] == "inactive" and value["SubState"] == "dead"
 and value["MainPID"] in ("", "0") and value["ControlPID"] in ("", "0")
 and not value["ControlGroup"] and not value["FragmentPath"] and not value["DropInPaths"],
 "GROWTH_UNLOADED_UNIT")
   require(all(not value[key] for key in ("Triggers", "TriggeredBy", "WantedBy", "RequiredBy",
 "UpheldBy", "OnSuccess", "OnFailure", "Job")),
 "GROWTH_UNLOADED_ACTIVATION")
  else:
   require(value["LoadState"] == "loaded", "GROWTH_UNIT_LOAD")
   validate_quiet_unit({key: value[key] for key in ("Id", "ActiveState", "SubState", "MainPID",
 "ControlPID", "Restart", "UnitFileState", "Triggers", "TriggeredBy", "WantedBy", "RequiredBy",
 "UpheldBy", "OnSuccess", "OnFailure", "Job", "Transient", "FragmentPath", "DropInPaths")})
  group=expected["control_group"]
  require(not value["ControlGroup"] or value["ControlGroup"] == group, "GROWTH_UNIT_CGROUP_CHANGED")
  result=dict(name=expected["name"], properties_sha256=digest(canonical(value)))
  if group is not None:
   result["cgroup"]=self.cgroup(group)
  return result
 def _process_reference_diagnostic(self, raw, field):
  # Describe the same failing comparison using only bytes already observed.
  # Indices/offsets locate private originals; argument/path values are not logged.
  path=os.fsdecode(raw).removesuffix(" (deleted)") if field != "cmdline" else None
  for index,root in enumerate(self.roots,1):
   root_raw=root.encode()
   offset=raw.find(root_raw) if field=="cmdline" else (0 if under(path,[root]) else -1)
   if offset<0:
    continue
   result=dict(field=field,comparison="byte_substring" if field=="cmdline" else "path_under_root",
root_index=index,root_bytes=len(root_raw),root_sha256=digest(root_raw),
value_bytes=len(raw),value_sha256=digest(raw),byte_offset=offset,
argument_index=None,argument_byte_offset=None,argument_bytes=None,argument_sha256=None,
match_at_argument_start=None,match_followed_by=None,
deleted_suffix_removed=field!="cmdline" and raw.endswith(b" (deleted)"))
   if field=="cmdline":
    begin=raw.rfind(b"\0",0,offset)+1
    end=raw.find(b"\0",offset)
    if end<0:end=len(raw)
    following=offset+len(root_raw)
    result.update(argument_index=raw.count(b"\0",0,offset),argument_byte_offset=offset-begin,
argument_bytes=end-begin,argument_sha256=digest(raw[begin:end]),
match_at_argument_start=offset==begin,
match_followed_by="argument_end" if following==end else "slash" if raw[following:following+1]==b"/" else "other")
   return result
  return None
 def _reject_process_reference(self, value, field):
  try:
   raw=value if type(value) is bytes else os.fsencode(value)
   detail=self._process_reference_diagnostic(raw,field)
   self.context["process_reference_diagnostic"]=detail if detail is not None else dict(status="UNAVAILABLE")
  except Exception:
   # A diagnostic error must not replace or allow the original refusal.
   self.context["process_reference_diagnostic"]=dict(status="UNAVAILABLE")
  raise r.ObservationError("GROWTH_BUSINESS_PROCESS")
 def processes(self):
  self.context=dict(operation="process_inventory",field="list")
  rows, total_fds=[], 0
  names=sorted(name for name in os.listdir("/proc") if name.isdecimal())
  require(len(names) <= 2048, "GROWTH_PROCESS_COUNT")
  self_pid=os.getpid()
  for name in names:
   self.context=dict(operation="process_inventory",pid=int(name),observer_pid=self_pid,
start_ticks=None,identity_rechecked=False,field="stat")
   self.check()
   prefix="/proc/" + name
   try:
    start_raw=read_kernel(prefix + "/stat", 4096, self.check, expected_fs=0x9FA0)
    start=process_start(start_raw)
    fields=start_raw.rpartition(b") ")[2].split()
    parent=fields[1] if len(fields)>1 else b""
    self.context.update(start_ticks=start,parent_pid=int(parent) if parent.isdigit() and len(parent)<=10 else None,
field="cmdline")
    cmdline=read_kernel(prefix + "/cmdline", 65536, self.check, expected_fs=0x9FA0)
    self.context["field"]="cgroup"
    cgroup=read_kernel(prefix + "/cgroup", 4096, self.check, expected_fs=0x9FA0)
    self.context.update(cgroup_bytes=len(cgroup),cgroup_sha256=digest(cgroup))
    if int(name) != self_pid:
     self.context["field"]="cmdline"
     if any(root.encode() in cmdline for root in self.roots):
      self._reject_process_reference(cmdline,"cmdline")
     for link in ("exe", "cwd"):
      self.context["field"]=link
      try:
       target=os.readlink(prefix + "/" + link)
      except FileNotFoundError:
       require(not cmdline, "GROWTH_PROCESS_LINK_UNKNOWN")
       continue
      if under(target.removesuffix(" (deleted)"), self.roots):
       self._reject_process_reference(target,link)
    self.context["field"]="fd"
    fd_directory=os.open(prefix + "/fd", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
     require(r.filesystem_type(fd_directory) == 0x9FA0, "GROWTH_PROCESS_FD_DIRECTORY")
     with os.scandir(fd_directory) as entries:
      for entry in entries:
       number=entry.name
       if not number.isdecimal():
        continue
       total_fds += 1
       require(total_fds <= 32768, "GROWTH_PROCESS_FD_COUNT")
       self.check()
       target=os.readlink(number, dir_fd=fd_directory).removesuffix(" (deleted)")
       if under(target, self.roots):
        info=read_kernel(prefix + "/fdinfo/" + number, 4096, self.check, expected_fs=0x9FA0)
        flags=re.findall(rb"^flags:\s+([0-7]+)$", info, re.M)
        require(len(flags) == 1, "GROWTH_PROCESS_FD_FLAGS")
        require(int(flags[0], 8) & os.O_ACCMODE == os.O_RDONLY, "GROWTH_UNKNOWN_WRITER")
    finally:
     os.close(fd_directory)
    self.context["field"]="maps"
    maps=read_kernel(prefix + "/maps", 1048576, self.check, expected_fs=0x9FA0)
    for line in maps.splitlines():
     fields=line.split(None, 5)
     if len(fields) == 6 and fields[1][1:2] == b"w" and fields[1][3:4] == b"s":
      mapped=os.fsdecode(fields[5]).removesuffix(" (deleted)")
      require(not under(mapped, self.roots), "GROWTH_MAPPED_WRITER")
    self.context["field"]="stat_recheck"
    require(process_start(read_kernel(prefix + "/stat", 4096, self.check, expected_fs=0x9FA0)) == start,
 "GROWTH_PROCESS_REUSE")
    self.context["identity_rechecked"]=True
    rows.append(dict(pid=int(name), start=start, cgroup_sha256=digest(cgroup)))
   except FileNotFoundError as error:
    raise r.ObservationError("GROWTH_PROCESS_INVENTORY_DRIFT") from error
  self.context=dict(operation="process_inventory",field="list_recheck")
  after=sorted(name for name in os.listdir("/proc") if name.isdecimal())
  require(names == after, "GROWTH_PROCESS_INVENTORY_DRIFT")
  self.context={}
  return dict(processes=len(rows), fd_count=total_fds, sha256=digest(canonical(rows)))
 def startup_manager(self, *, user_uid=None):
  manager="user" if user_uid is not None else "system"
  declared=sorted((row for row in self.description["domain_units"]
 if row["manager"]==manager),key=lambda row:row["name"])
  names=[row["name"] for row in declared]
  observed=self.show_many(names,user_uid=user_uid) if names else {}
  domains=[]
  for item in declared:
   self.check()
   self.context=dict(manager="user_1100" if user_uid is not None else "system",unit=item["name"])
   value=observed[item["name"]]
   require(value["Id"] == item["name"], "GROWTH_DOMAIN_UNIT_IDENTITY")
   require(value["LoadState"] in ("loaded", "not-found") and
 value["ControlGroup"] in ("", item["control_group"]), "GROWTH_DOMAIN_UNIT")
   require(item["name"].endswith(".slice") and not any(value[key] for key in self.SHOW if key.startswith("Exec")),
 "GROWTH_DOMAIN_UNIT_ACTION")
   domains.append(dict(name=item["name"], properties_sha256=digest(canonical(value))))
  return dict(scope="DECLARED_ONLY",domains=domains,
 undeclared_unit_inventory="NOT_PERFORMED",indirect_startup="NOT_PERFORMED")
 def startup(self):
  result={"system": self.startup_manager()}
  if any(item["manager"] == "user" for item in self.description["domain_units"]):
   result["user_1100"]=self.startup_manager(user_uid=1100)
  return result
 def persistent(self):
  self.context=dict(operation="persistent_inventory",field="mountinfo")
  mounts=r.mounts(r.kernel_read("/proc/self/mountinfo", 1048576, self.check))
  records=[];retained=[]
  roots=retained_quota_roots(self.description) if "retained_quota_roots" in self.description else {}
  for index,path in enumerate(self.description["essential_paths"]):
   self.context=dict(operation="persistent_inventory",field="open",path_index=index,
 path_bytes=len(path),path_sha256=digest(path.encode("ascii")))
   self.check()
   held=None
   if path in roots:fd,held=open_path(path,directory=True,owners=(0,1100),retained=roots[path])
   else:fd=open_path(path, owners=(0, 1100))
   try:
    self.context["field"]="stat"
    info=os.fstat(fd)
    require(held is None or r.identity(info)==held,"GROWTH_RETAINED_ROOT_DRIFT")
    require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), "GROWTH_ESSENTIAL_OBJECT")
    self.context["field"]="mount_id"
    mid=r.mount_id(r.kernel_read("/proc/self/fdinfo/" + str(fd), 4096, self.check))
    require(mid in mounts, "GROWTH_ESSENTIAL_MOUNT")
    self.context["field"]="filesystem_uuid"
    filesystem=dict(mount=mounts[mid], uuid=r.fs_uuid(fd))
    self.context["field"]="filesystem_validation"
    validate_durable_filesystem(filesystem)
    require(filesystem["mount"]["device"] == info.st_dev, "GROWTH_ESSENTIAL_DEVICE")
    records.append(dict(path_sha256=digest(path.encode()), filesystem_uuid=filesystem["uuid"],
 identity=r.identity(info)))
    if held is not None:retained.append(records[-1])
   finally:
    os.close(fd)
  result=dict(count=len(records),sha256=digest(canonical(records)))
  if roots:
   sample=dict(count=len(retained),sha256=digest(canonical(retained)))
   expected=retained_sample(self.description["pre_report"],self.description) if self.description.get("phase")=="post" else getattr(self,"retained_snapshot",sample)
   require(sample==expected,"GROWTH_RETAINED_ROOT_DRIFT")
   self.retained_snapshot=sample;result["retained_roots"]=sample
  self.context={}
  return result
 def collect(self):
  units=[self.quiet_service(item) for item in self.description["expected_units"]]
  groups=[self.cgroup(path) for path in self.description["domain_cgroups"]]
  startup=self.startup()
  processes=self.processes()
  persistent=self.persistent()
  require(groups == [self.cgroup(path) for path in self.description["domain_cgroups"]], "GROWTH_DOMAIN_DRIFT")
  require(units == [self.quiet_service(item) for item in self.description["expected_units"]], "GROWTH_UNIT_DRIFT")
  return dict(units=units, domain_cgroups=groups, startup=startup,
 processes=processes, persistent=persistent, historical_exit="UNKNOWN")
def metadata(value):
 return {name: getattr(value, "st_" + name) for name in
 ("dev", "ino", "mode", "uid", "gid", "nlink", "size", "mtime_ns", "ctime_ns", "atime_ns")}
def preservation(value):
 return {name: value[name] for name in
 ("ino", "mode", "uid", "gid", "nlink", "size", "mtime_ns", "atime_ns")}
def file_hash(fd, remaining, check):
 before=metadata(os.fstat(fd))
 require(stat.S_ISREG(before["mode"]) and before["size"] <= remaining, "GROWTH_TREE_BYTES")
 h, count=hashlib.sha256(), 0
 while True:
  check()
  raw=os.read(fd, min(65536, remaining + 1 - count))
  check()
  if not raw:
   break
  count += len(raw)
  require(count <= remaining, "GROWTH_TREE_BYTES")
  h.update(raw)
 require(count == before["size"] and before == metadata(os.fstat(fd)), "GROWTH_TREE_FILE_DRIFT")
 return h.hexdigest(), count
def tree_digest(root_fd, check, *, max_bytes=MAX_BYTES, max_entries=MAX_ENTRIES, mount_id=None):
 require(callable(mount_id), "GROWTH_TREE_MOUNT_CHECK")
 require(fcntl.fcntl(root_fd, fcntl.F_GETFL) & os.O_NOATIME, "GROWTH_TREE_NOATIME")
 root_info=os.fstat(root_fd)
 require(stat.S_ISDIR(root_info.st_mode), "GROWTH_TREE_ROOT")
 root_mount=mount_id(root_fd)
 rows, nodes, content_bytes=[], [], 0
 stack=[(root_fd, "", False)]
 try:
  while stack:
   fd, path, owned=stack.pop()
   if owned:
    nodes.append(fd)
   check()
   before=metadata(os.fstat(fd))
   require(before["dev"] == root_info.st_dev and mount_id(fd) == root_mount,
 "GROWTH_TREE_CROSS_MOUNT")
   require(stat.S_ISDIR(before["mode"]), "GROWTH_TREE_DIRECTORY")
   names=[]
   with os.scandir(fd) as entries:
    for entry in entries:
     check()
     names.append(entry.name)
     require(len(rows) + len(stack) + len(names) + 1 <= max_entries,
 "GROWTH_TREE_ENTRIES")
   names.sort()
   rows.append(dict(path=path, metadata=before))
   for name in names:
    check()
    require(name not in (".", "..") and "/" not in name and "\0" not in name,
 "GROWTH_TREE_NAME")
    encoded=os.fsencode(name)
    require(len(encoded) <= 255 and encoded.decode("utf-8", "strict") == name,
 "GROWTH_TREE_ENCODING")
    child_path=path + "/" + name
    require(len(child_path.encode("utf-8")) <= 4096, "GROWTH_TREE_PATH")
    info=os.stat(name, dir_fd=fd, follow_symlinks=False)
    require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode), "GROWTH_TREE_OBJECT")
    child=os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC
 | os.O_NONBLOCK | (os.O_DIRECTORY if stat.S_ISDIR(info.st_mode) else 0), dir_fd=fd)
    try:
     require(metadata(os.fstat(child)) == metadata(info), "GROWTH_TREE_NAME_DRIFT")
     require(info.st_dev == root_info.st_dev and mount_id(child) == root_mount,
 "GROWTH_TREE_CROSS_MOUNT")
     if stat.S_ISDIR(info.st_mode):
      require(len(stack) + len(nodes) < 64, "GROWTH_TREE_FDS")
      stack.append((child, child_path, True))
      child=None
     else:
      sha, count=file_hash(child, max_bytes - content_bytes, check)
      content_bytes += count
      rows.append(dict(path=child_path, metadata=metadata(info), sha256=sha))
     require(metadata(os.stat(name, dir_fd=fd, follow_symlinks=False)) == metadata(info),
 "GROWTH_TREE_NAME_DRIFT")
     require(len(rows) + len(stack) <= max_entries, "GROWTH_TREE_ENTRIES")
    finally:
     if child is not None:
      os.close(child)
   require(metadata(os.fstat(fd)) == before, "GROWTH_TREE_DIRECTORY_DRIFT")
   if owned:
    nodes.remove(fd)
    os.close(fd)
  rows.sort(key=lambda row: row["path"])
  require(len(rows) <= max_entries and content_bytes <= max_bytes, "GROWTH_TREE_LIMIT")
  for row in rows:
   check()
   fd=os.dup(root_fd)
   try:
    for name in row["path"].split("/")[1:]:
     next_fd=os.open(name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
     os.close(fd)
     fd=next_fd
     require(not stat.S_ISLNK(os.fstat(fd).st_mode), "GROWTH_TREE_REOPEN_LINK")
    require(metadata(os.fstat(fd)) == row["metadata"] and mount_id(fd) == root_mount,
 "GROWTH_TREE_FINAL_DRIFT")
   finally:
    os.close(fd)
  preserved=[dict(path=row["path"], metadata=preservation(row["metadata"]),
 **({"sha256": row["sha256"]} if "sha256" in row else {})) for row in rows]
  return dict(entries=len(rows), content_bytes=content_bytes,
 sha256=digest(canonical(preserved)), observation_sha256=digest(canonical(rows)))
 finally:
  for fd in nodes:
   os.close(fd)
  for fd, _, owned in stack:
   if owned:
    os.close(fd)
def verify_preservation(before, after):
 require(set(before) == set(after) == {"entries", "content_bytes", "sha256", "observation_sha256"},
 "GROWTH_TREE_REPORT")
 require(all(before[key] == after[key] for key in ("entries", "content_bytes", "sha256")),
 "GROWTH_TREE_CHANGED")
def validate_quiet_unit(value):
 """A unit alone does NOT prove boot quietness or durable old evidence."""
 require(type(value) is dict and set(value) == {"Id", "ActiveState", "SubState", "MainPID",
 "ControlPID", "Restart", "UnitFileState", "Triggers", "TriggeredBy", "WantedBy", "RequiredBy",
 "UpheldBy", "OnSuccess", "OnFailure", "Job", "Transient", "FragmentPath", "DropInPaths"},
 "GROWTH_UNIT_FIELDS")
 require(value["ActiveState"] in ("inactive", "failed") and value["SubState"] in ("dead", "failed")
 and value["MainPID"] == value["ControlPID"] == "0" and value["Restart"] == "no",
 "GROWTH_UNIT_ACTIVE")
 require(value["UnitFileState"] in ("", "disabled", "static", "transient")
 and all(not value[key] for key in ("Triggers", "TriggeredBy", "WantedBy", "RequiredBy",
 "UpheldBy", "OnSuccess", "OnFailure", "Job")),
 "GROWTH_UNIT_AUTOSTART")
 return value
def validate_durable_filesystem(row):
 require(row["mount"]["fstype"] == "ext4" and row["mount"]["root"] == "/"
 and "rw" in row["mount"]["options"] and row["uuid"], "GROWTH_VOLATILE_EVIDENCE")
def validate_completion(before_rows, after_rows):
 require(len(before_rows) == len(after_rows) == 5, "GROWTH_PARENT_COUNT")
 for before, after in zip(before_rows, after_rows):
  require(before["role"] == after["role"] and before["path"] == after["path"]
 and before["filesystem"]["uuid"] == after["filesystem"]["uuid"], "GROWTH_PARENT_IDENTITY")
  for key in ("ino", "mode", "uid", "gid"):
   require(before["directory"][key] == after["directory"][key], "GROWTH_PARENT_DIRECTORY")
  for key in ("root", "path", "fstype", "options"):
   require(before["filesystem"]["mount"][key] == after["filesystem"]["mount"][key],
 "GROWTH_PARENT_MOUNT")
  if after["role"] == "journal":
   require(after["available"]["bytes"] >= 400 * 1048576 and after["available"]["inodes"] >= 32768,
 "GROWTH_TARGET_CAPACITY")
PRE_FIELDS={"schema", "session", "phase", "status", "nonce", "source_binding_sha256", "boot_id", "runtime_preparation",
 "rows", "tree", "journal_device", "resize2fs", "quiescence", "resource_observation", "guest_startup_assurance"}
def validate_pre_report(value, description):
 require(type(value) is dict and set(value) == PRE_FIELDS and value["schema"] == REPORT_SCHEMA
 and value["session"] == SESSION and value["phase"] == "pre" and value["status"] == "GUEST_QUIET"
 and value["nonce"] == description["nonce"]
 and value["source_binding_sha256"] == description["source_binding_sha256"]
 and value["boot_id"] == description["original_boot_id"], "GROWTH_PRE_REPORT")
 validate_startup_assurance(value["guest_startup_assurance"])
 validate_startup_assurance(description.get("guest_startup_assurance"))
 same_parents(description["saved_rows"], value["rows"])
 tree=value["tree"]
 require(type(tree) is dict and set(tree) == {"entries", "content_bytes", "sha256", "observation_sha256"},
 "GROWTH_PRE_TREE")
 r.integer(tree["entries"], 1, MAX_ENTRIES); r.integer(tree["content_bytes"], 0, MAX_BYTES)
 sha_value(tree["sha256"]); sha_value(tree["observation_sha256"])
 journal=value["journal_device"]
 require(type(journal) is dict and journal.get("block_bytes") == OLD_SIZE and
 journal.get("serial") == description["journal_serial"] and
 journal.get("uuid") == description["saved_rows"][3]["filesystem"]["uuid"], "GROWTH_PRE_JOURNAL")
 tool=value["resize2fs"]
 require(type(tool) is dict and set(tool) == {"path", "identity", "bytes", "sha256", "version_sha256"}
 and tool["path"] == "/usr/sbin/resize2fs", "GROWTH_PRE_TOOL")
 sha_value(tool["sha256"]); sha_value(tool["version_sha256"])
 require(type(value["quiescence"]) is dict and value["quiescence"].get("historical_exit") == "UNKNOWN",
 "GROWTH_PRE_QUIESCENCE")
 validate_startup_report(value["quiescence"].get("startup"),description)
 if "retained_quota_roots" in description:retained_sample(value,description)
 validate_runtime_report(value["runtime_preparation"],description,value["boot_id"],"pre")
 validate_resources(value["resource_observation"])
 return value
def validate_resources(value):
 counters={"self_cpu_microseconds", "exited_children_cpu_microseconds", "self_peak_rss_bytes", "exited_child_peak_rss_bytes"}
 require(type(value) is dict and set(value) == counters | {"coverage", "complete"}
 and value["coverage"] == "THROUGH_REPORT_ONLY" and value["complete"] is False, "GROWTH_RESOURCE_REPORT")
 for key in counters:
  r.integer(value[key])
 require(value["self_cpu_microseconds"] + value["exited_children_cpu_microseconds"] <= 120000000
 and max(value["self_peak_rss_bytes"], value["exited_child_peak_rss_bytes"]) <= 512 * 1048576,
 "GROWTH_RESOURCE_REPORT_LIMIT")
def validate_post_report(value, description):
 before=validate_pre_report(description["pre_report"], description)
 fields=PRE_FIELDS | {"original_boot_id", "pre_report_sha256", "resize_result"}
 require(type(value) is dict and set(value) == fields and value["schema"] == REPORT_SCHEMA
 and value["session"] == SESSION and value["phase"] == "post" and value["status"] == "FILESYSTEM_GROWN"
 and value["nonce"] == description["nonce"]
 and value["source_binding_sha256"] == description["source_binding_sha256"]
 and value["original_boot_id"] == description["original_boot_id"]
 and value["pre_report_sha256"] == description["pre_report_sha256"] == digest(canonical(before)),
 "GROWTH_POST_REPORT")
 validate_startup_assurance(value["guest_startup_assurance"])
 validate_startup_assurance(description.get("guest_startup_assurance"))
 uuid_value(value["boot_id"])
 require(value["boot_id"] != value["original_boot_id"], "GROWTH_POST_BOOT")
 validate_completion(before["rows"], value["rows"])
 verify_preservation(before["tree"], value["tree"])
 require(value["resize2fs"] == before["resize2fs"], "GROWTH_POST_TOOL")
 current, old=value["journal_device"], before["journal_device"]
 require(set(current) == set(old) == {"path", "uuid", "serial", "block_bytes", "node", "superblock"}
 and current["block_bytes"] == NEW_SIZE
 and re.fullmatch(r"/dev/vd[a-z]+", current["path"])
 and all(current[key] == old[key] for key in ("uuid", "serial", "node")), "GROWTH_POST_DEVICE")
 require(current["superblock"]["filesystem_bytes"] == NEW_SIZE and
 all(current["superblock"][key] == old["superblock"][key] for key in ("uuid", "features", "block_size")),
 "GROWTH_POST_FILESYSTEM")
 resize=value["resize_result"]
 require(type(resize) is dict and set(resize) == {"returncode", "both_eof", "stdout_bytes", "stderr_bytes",
 "stdout_sha256", "stderr_sha256"}
 and type(resize["returncode"]) is int and resize["returncode"] == 0 and resize["both_eof"] is True,
 "GROWTH_POST_RESIZE_RESULT")
 for stream in ("stdout", "stderr"):
  r.integer(resize[stream + "_bytes"], 0, STREAM_LIMIT)
  sha_value(resize[stream + "_sha256"])
 require(type(value["quiescence"]) is dict and value["quiescence"].get("historical_exit") == "UNKNOWN",
 "GROWTH_POST_QUIESCENCE")
 validate_startup_report(value["quiescence"].get("startup"),description)
 if "retained_quota_roots" in description:
  require(retained_sample(value,description)==retained_sample(before,description),"GROWTH_RETAINED_ROOT_DRIFT")
 validate_runtime_report(value["runtime_preparation"],description,value["boot_id"],"post")
 validate_resources(value["resource_observation"])
 return value
def continue_token(nonce, report_sha256):
 sha_value(nonce); sha_value(report_sha256)
 return ("POWER_OFF " + SESSION + " " + nonce + " " + report_sha256 + "\n").encode("ascii")
def emit(value, fd=1):
 raw=canonical(value)
 require(len(raw) <= STREAM_LIMIT, "GROWTH_REPORT_LIMIT")
 offset=0
 while offset < len(raw):
  count=os.write(fd, raw[offset:])
  require(count > 0, "GROWTH_REPORT_WRITE")
  offset += count
def receive_token(expected, check, *, fd=0):
 raw=bytearray()
 while len(raw) <= len(expected):
  check()
  ready, _, _=select.select([fd], [], [], 0.05)
  if not ready:
   continue
  part=os.read(fd, len(expected) + 1 - len(raw))
  if not part:
   break
  raw.extend(part)
  require(len(raw) <= len(expected), "GROWTH_CONTINUE_LIMIT")
  if len(raw) == len(expected):
   continue
 require(bytes(raw) == expected, "GROWTH_CONTINUE_TOKEN")
 check()
RUNTIME_SHOW=("Id","LoadState","ActiveState","SubState","ControlGroup","InvocationID","Job",
 "FragmentPath","DropInPaths","MemoryMax","MemorySwapMax","TasksMax","CPUQuotaPerSecUSec",
 "Delegate","User","MainPID","ControlPID")
def validate_runtime_report(value, description, current_boot, phase):
 binding=validate_runtime_binding(description["runtime_parent_binding"],description)
 require(type(value) is dict and set(value)=={"schema","binding_sha256","nonce","boot_id","phase",
 "commands","configs","directories","pools","parents","manager","bus","elapsed_ns","tool"}
 and len(canonical(value))<=16384 and value["schema"]=="lhq-runtime-preparation/v1"
 and value["binding_sha256"]==digest(canonical(binding)) and value["nonce"]==description["nonce"]
 and value["boot_id"]==current_boot and value["phase"]==phase,"GROWTH_RUNTIME_REPORT")
 r.integer(value["elapsed_ns"],0,60000000000)
 require(type(value["commands"]) is list and 5<=len(value["commands"])<=12,"GROWTH_RUNTIME_COMMANDS")
 seen=set()
 allowed={"guard_units","system_before","system_reload","system_start","system_after",
 "user_before","user_reload","user_start","user_after"}
 for row in value["commands"]:
  require(type(row) is dict and set(row)=={"step","arguments","arguments_sha256","returncode","both_eof","stdout_bytes",
 "stderr_bytes","stdout_sha256","stderr_sha256"} and row["step"] in allowed-seen
 and row["returncode"] in ((0,1) if row["step"].endswith("before") else (0,))
 and type(row["returncode"]) is int and row["both_eof"] is True and row["stderr_bytes"]==0,
 "GROWTH_RUNTIME_COMMAND_RESULT")
  seen.add(row["step"])
  args=row["arguments"];step=row["step"]
  require(type(args) is list and all(type(v) is str for v in args)
 and digest(canonical(args))==row["arguments_sha256"],"GROWTH_RUNTIME_COMMAND_BINDING")
  names=([binding["parents"]["retained_ordinary"]["unit"]] if step.startswith("user_") else
 [parent["unit"] for parent in binding["parents"].values() if parent["manager"]=="system"]
 +["user-runtime-dir@1100.service",binding["manager"]["unit"]])
  if step=="guard_units":names=[item["name"] for item in description["expected_units"]]
  if step.endswith("reload"):require(args==["daemon-reload"],"GROWTH_RUNTIME_COMMAND_POLICY")
  elif step.endswith("start"):
   require(args[:2]==["start","--"] and 0<len(args[2:])==len(set(args[2:]))
 and set(args[2:])<=set(names),"GROWTH_RUNTIME_COMMAND_POLICY")
  else:
   require(args[:4]==["show","--all","--property="+",".join(GuestInventory.SHOW if step=="guard_units" else RUNTIME_SHOW),"--"]
 and len(args[4:])==len(names) and set(args[4:])==set(names),"GROWTH_RUNTIME_COMMAND_POLICY")
  for key in ("arguments_sha256","stdout_sha256","stderr_sha256"):sha_value(row[key])
  r.integer(row["stdout_bytes"],0,STREAM_LIMIT)
 require({"guard_units","system_before","system_after","user_before","user_after"}<=seen,"GROWTH_RUNTIME_COMMAND_COVERAGE")
 order=("guard_units","system_before","system_reload","system_start","system_after","user_before","user_reload","user_start","user_after")
 require([row["step"] for row in value["commands"]]==[step for step in order if step in seen],"GROWTH_RUNTIME_COMMAND_ORDER")
 require(type(value["parents"]) is dict and set(value["parents"])==set(RUNTIME_ROLES),"GROWTH_RUNTIME_PARENT_REPORT")
 for role,row in value["parents"].items():
  require(type(row) is dict and set(row)=={"properties","cgroup"},"GROWTH_RUNTIME_PARENT_REPORT")
  _runtime_properties(row["properties"],binding["parents"][role],active=True)
  group=row["cgroup"]
  require(type(group) is dict and group.get("state")=="UNPOPULATED"
 and group.get("path")==binding["parents"][role]["control_group"],"GROWTH_RUNTIME_PARENT_GROUP")
 _runtime_properties(value["manager"],dict(binding["parents"]["retained_ordinary"],
 unit=binding["manager"]["unit"],control_group=binding["manager"]["control_group"]),active=True,manager=True)
 require(type(value["configs"]) is list and len(value["configs"])==7
 and type(value["directories"]) is list and len(value["directories"])<=2,"GROWTH_RUNTIME_CONFIG_REPORT")
 expected={role:runtime_config(row) for role,row in binding["parents"].items()}
 expected["manager"]=runtime_config(binding["parents"]["retained_ordinary"],manager=True)
 command_steps=seen
 seen=set();created=0
 for row in value["configs"]:
  require(type(row) is dict and set(row)=={"role","path","identity","bytes","sha256","created"}
 and row["role"] in set(expected)-seen and type(row["created"]) is bool
 and row["bytes"]==len(expected[row["role"]]) and row["sha256"]==digest(expected[row["role"]]),"GROWTH_RUNTIME_CONFIG_REPORT")
  role=row["role"];seen.add(role);created+=int(row["created"])
  if role=="manager":paths=["/etc/systemd/system/user@1100.service.d/50-local-hand-q2.conf"]
  elif role=="retained_ordinary":paths=["/run/user/1100/systemd/user/"+binding["parents"][role]["unit"]]
  else:paths=[prefix+binding["parents"][role]["unit"] for prefix in
 ("/run/systemd/system/","/etc/systemd/system/","/usr/lib/systemd/system/")]
  require(row["path"] in paths and (not row["created"] or role in ("ordinary","retained_ordinary")),"GROWTH_RUNTIME_CONFIG_PATH")
  ident=row["identity"];uid=1100 if role=="retained_ordinary" else 0
  require(type(ident) is list and len(ident)==6 and all(type(n) is int and n>=0 for n in ident)
 and ident[2:]==[stat.S_IFREG|0o644,uid,uid,1],"GROWTH_RUNTIME_CONFIG_IDENTITY")
  require(not row["created"] or row["path"].startswith("/run/"),"GROWTH_RUNTIME_CONFIG_CREATE_PATH")
 require(created<=2 and sum(row["bytes"] for row in value["configs"] if row["created"])<=8192,"GROWTH_RUNTIME_CONFIG_BOUND")
 for role,step in (("ordinary","system_reload"),("retained_ordinary","user_reload")):
  require(next(row["created"] for row in value["configs"] if row["role"]==role)==(step in command_steps),"GROWTH_RUNTIME_RELOAD_BINDING")
 paths=set()
 for row in value["directories"]:
  require(type(row) is dict and set(row)=={"path","identity"} and row["path"] in
 {"/run/user/1100/systemd","/run/user/1100/systemd/user"}-paths,"GROWTH_RUNTIME_DIRECTORY_REPORT")
  paths.add(row["path"]);ident=row["identity"]
  require(type(ident) is list and len(ident)==6 and all(type(n) is int and n>=0 for n in ident)
 and ident[2:5]==[stat.S_IFDIR|0o755,1100,1100],"GROWTH_RUNTIME_DIRECTORY_IDENTITY")
 require(type(value["pools"]) is list and 1<=len(value["pools"])<=2
 and len({row["dev"] for row in value["pools"]})==len(value["pools"]),"GROWTH_RUNTIME_POOLS")
 for pool in value["pools"]:
  require(type(pool) is dict and set(pool)=={"dev","reserved_bytes","reserved_inodes","before","after"}
 and pool["reserved_bytes"]==8192*(1 if phase=="pre" else 2)
 and pool["reserved_inodes"]==32*(1 if phase=="pre" else 2),"GROWTH_RUNTIME_POOL_RESERVE")
  for when in ("before","after"):
   require(type(pool[when]) is list and len(pool[when])==2
 and pool[when][0]>=pool["reserved_bytes"] and pool[when][1]>=pool["reserved_inodes"],"GROWTH_RUNTIME_POOL_CAPACITY")
 require(type(value["bus"]) is dict and set(value["bus"])=={"runtime","bus","private"},"GROWTH_RUNTIME_BUS_REPORT")
 for key,row in value["bus"].items():
  require(type(row) is list and len(row)==6 and all(type(n) is int and n>=0 for n in row)
 and row[3:5]==[1100,1100] and (row[2]==stat.S_IFDIR|0o700 if key=="runtime" else stat.S_ISSOCK(row[2])),"GROWTH_RUNTIME_BUS_IDENTITY")
 tool=value["tool"]
 require(type(tool) is dict and set(tool)=={"path","identity","bytes","sha256"}
 and tool["path"]=="/usr/bin/systemctl","GROWTH_RUNTIME_TOOL")
 r.integer(tool["bytes"],1,16*1048576);sha_value(tool["sha256"])
 ident=tool["identity"]
 require(type(ident) is dict and set(ident)=={"dev","ino","mode","uid","gid","nlink"}
 and all(type(n) is int and n>=0 for n in ident.values()) and ident["uid"]==ident["gid"]==0
 and ident["nlink"]==1 and stat.S_ISREG(ident["mode"]) and ident["mode"]&0o111
 and not ident["mode"]&0o022,"GROWTH_RUNTIME_TOOL_IDENTITY")
 return value
def _runtime_properties(value, row, *, active, manager=False):
 require(type(value) is dict and set(value)==set(RUNTIME_SHOW) and value["Id"]==row["unit"]
 and value["Job"]=="" and value["ControlPID"] in ("","0"),"GROWTH_RUNTIME_PROPERTIES")
 require((value["ActiveState"],value["SubState"]) in
 (("active","running" if manager else "active"),) if active else
 (value["ActiveState"],value["SubState"]) in (("inactive","dead"),("active","running" if manager else "active")),
 "GROWTH_RUNTIME_STATE")
 if value["LoadState"]=="not-found":
  require(not active and value["ActiveState"]=="inactive" and not any(value[k] for k in
 ("FragmentPath","DropInPaths","ControlGroup","InvocationID")) and value["MainPID"] in ("","0"),"GROWTH_RUNTIME_MISSING")
  return
 require(value["LoadState"]=="loaded" and value["MemoryMax"]==str(row["memory_bytes"])
 and value["TasksMax"]==str(row["tasks_max"]) and value["MemorySwapMax"]=="0"
 and value["CPUQuotaPerSecUSec"]=="1s","GROWTH_RUNTIME_LIMITS")
 if value["ActiveState"]=="active":
  require(value["ControlGroup"]==row["control_group"] and re.fullmatch(r"[0-9a-f]{32}",value["InvocationID"]),"GROWTH_RUNTIME_CURRENT_IDENTITY")
 else:require(value["ControlGroup"] in ("",row["control_group"]),"GROWTH_RUNTIME_CURRENT_GROUP")
 if manager:require(value["User"]=="1100" and value["Delegate"]=="yes","GROWTH_RUNTIME_DELEGATE")
 else:require(value["MainPID"] in ("","0") and not value["DropInPaths"],"GROWTH_RUNTIME_SLICE_ACTION")
def runtime_summary(report):
 value=report["runtime_preparation"]
 return dict(schema="lhq-runtime-transition/v1",binding_sha256=value["binding_sha256"],nonce=value["nonce"],
 phase=value["phase"],boot_id=value["boot_id"],report_sha256=digest(canonical(report)),
 runtime_sha256=digest(canonical(value)),commands_sha256=digest(canonical(value["commands"])),
 configs_sha256=digest(canonical(value["configs"])),elapsed_ns=value["elapsed_ns"],
 parents={role:dict(unit=row["properties"]["Id"],control_group=row["properties"]["ControlGroup"],
 invocation_id=row["properties"]["InvocationID"],identity=row["cgroup"]["identity"])
 for role,row in value["parents"].items()},manager={key:value["manager"][key] for key in
 ("Id","ControlGroup","InvocationID")},pools=value["pools"])
def validate_runtime_summaries(value,binding,nonce,boots,reports):
 validate_runtime_binding(binding)
 require(type(value) is dict and set(value)=={"pre","post"},"GROWTH_RUNTIME_SUMMARIES")
 for phase,row in value.items():
  require(type(row) is dict and set(row)=={"schema","binding_sha256","nonce","phase","boot_id","report_sha256",
 "runtime_sha256","commands_sha256","configs_sha256","elapsed_ns","parents","manager","pools"}
 and row["schema"]=="lhq-runtime-transition/v1" and row["binding_sha256"]==digest(canonical(binding))
 and row["nonce"]==nonce and row["phase"]==phase and row["boot_id"]==boots[phase]
 and row["report_sha256"]==reports[phase]["sha256"],"GROWTH_RUNTIME_SUMMARY_BINDING")
  for name in ("runtime_sha256","commands_sha256","configs_sha256"):sha_value(row[name])
  r.integer(row["elapsed_ns"],0,60000000000)
  require(type(row["parents"]) is dict and set(row["parents"])==set(RUNTIME_ROLES),"GROWTH_RUNTIME_SUMMARY_PARENTS")
  for role,item in row["parents"].items():
   require(type(item) is dict and set(item)=={"unit","control_group","invocation_id","identity"}
 and all(item[key]==binding["parents"][role][key] for key in ("unit","control_group"))
 and re.fullmatch(r"[0-9a-f]{32}",item["invocation_id"] or ""),"GROWTH_RUNTIME_SUMMARY_PARENT")
   require(type(item["identity"]) is dict and set(item["identity"])==set(r.IDENTITY),"GROWTH_RUNTIME_SUMMARY_IDENTITY")
   for v in item["identity"].values():r.integer(v)
  require(type(row["manager"]) is dict and set(row["manager"])=={"Id","ControlGroup","InvocationID"}
 and row["manager"]["Id"]==binding["manager"]["unit"] and row["manager"]["ControlGroup"]==binding["manager"]["control_group"]
 and re.fullmatch(r"[0-9a-f]{32}",row["manager"]["InvocationID"] or ""),"GROWTH_RUNTIME_SUMMARY_MANAGER")
  require(type(row["pools"]) is list and 1<=len(row["pools"])<=2,"GROWTH_RUNTIME_SUMMARY_POOLS")
  for pool in row["pools"]:
   require(type(pool) is dict and set(pool)=={"dev","reserved_bytes","reserved_inodes","before","after"}
 and pool["reserved_bytes"]==8192*(1 if phase=="pre" else 2)
 and pool["reserved_inodes"]==32*(1 if phase=="pre" else 2),"GROWTH_RUNTIME_SUMMARY_POOL")
   r.integer(pool["dev"])
   for key in ("before","after"):
    require(type(pool[key]) is list and len(pool[key])==2 and all(type(n) is int for n in pool[key])
 and pool[key][0]>=pool["reserved_bytes"] and pool[key][1]>=pool["reserved_inodes"],"GROWTH_RUNTIME_SUMMARY_CAPACITY")
 return value
class RuntimePreparation:
 """One fixed pre/post preparation, inside the existing maintenance budgets."""
 def __init__(self,maintenance,boot):
  self.m=maintenance;self.inventory=maintenance.inventory;self.description=maintenance.description
  self.binding=validate_runtime_binding(self.description["runtime_parent_binding"],self.description)
  self.start=(time.monotonic_ns(),time.clock_gettime_ns(time.CLOCK_BOOTTIME))
  self.previous=self.start;self.pool_fds={};self.config_fds=[];self.used=set()
  self.report=dict(schema="lhq-runtime-preparation/v1",binding_sha256=digest(canonical(self.binding)),
 nonce=self.description["nonce"],boot_id=boot,phase=self.description["phase"],commands=[],configs=[],directories=[],
 pools=[],parents={},manager={},bus={},elapsed_ns=0,tool=self.inventory.systemctl)
 def check(self):
  self.m.window.check(change=True)
  now=(time.monotonic_ns(),time.clock_gettime_ns(time.CLOCK_BOOTTIME))
  require(all(p<=n<s+60000000000 for p,n,s in zip(self.previous,now,self.start)),"GROWTH_RUNTIME_DEADLINE")
  self.previous=now;self.report["elapsed_ns"]=max(n-s for n,s in zip(now,self.start))
 def command(self,step,args,*,user=False,missing=False):
  self.check();require(step not in self.used and len(self.used)<12,"GROWTH_RUNTIME_COMMAND_REPLAY")
  self.used.add(step)
  row=dict(step=step,arguments=list(args),arguments_sha256=digest(canonical(args)));self.report["commands"].append(row)
  old=self.inventory.check;self.inventory.check=self.check
  try:return self.inventory.ctl(args,user_uid=1100 if user else None,runtime_missing=missing)
  finally:
   self.inventory.check=old
   if self.inventory.last_result is not None:row.update(self.inventory.last_result)
 def show(self,step,names,*,user=False,missing=False):
  raw=self.command(step,["show","--all","--property="+",".join(RUNTIME_SHOW),"--",*names],user=user,missing=missing)
  rows={}
  for block in raw.decode("utf-8","strict").strip().split("\n\n"):
   fields=[line.split("=",1) for line in block.splitlines()]
   require(all(len(row)==2 for row in fields) and len({row[0] for row in fields})==len(fields),"GROWTH_RUNTIME_SHOW_FORMAT")
   value=dict(fields)
   require(set(value)<=set(RUNTIME_SHOW) and {"Id","LoadState","ActiveState","SubState"}<=set(value)
 and value["Id"] in names and value["Id"] not in rows,"GROWTH_RUNTIME_SHOW_SET")
   rows[value["Id"]]={key:value.get(key,"") for key in RUNTIME_SHOW}
  require(set(rows)==set(names),"GROWTH_RUNTIME_SHOW_SET")
  require(self.inventory.last_result["returncode"]==0 or missing and any(row["LoadState"]=="not-found" for row in rows.values()),"GROWTH_RUNTIME_SHOW_EXIT")
  return rows
 def pool(self,path):
  self.inventory.context=dict(operation="runtime_pool",field="open",
 path_bytes=len(path),path_sha256=digest(path.encode("ascii")))
  self.check();fd=open_path(path,directory=True,owners=(0,1100))
  try:
   self.inventory.context["field"]="stat"
   info=os.fstat(fd)
   self.inventory.context["field"]="filesystem_type"
   require(r.filesystem_type(fd)==0x01021994,"GROWTH_RUNTIME_TMPFS")
   if info.st_dev in self.pool_fds:
    self.inventory.context={};return
   self.inventory.context["field"]="capacity"
   size=os.fstatvfs(fd);count=1 if self.description["phase"]=="pre" else 2
   row=dict(dev=info.st_dev,reserved_bytes=8192*count,reserved_inodes=32*count,
 before=[size.f_bavail*size.f_frsize,size.f_favail],after=[])
   require(row["before"][0]>=row["reserved_bytes"] and row["before"][1]>=row["reserved_inodes"],"GROWTH_RUNTIME_CAPACITY")
   self.report["pools"].append(row);self.pool_fds[info.st_dev]=(fd,row);fd=None
   self.inventory.context={}
  finally:
   if fd is not None:os.close(fd)
 def absent(self,path):
  self.check()
  try:fd=open_path(path,owners=(0,1100))
  except FileNotFoundError:return
  os.close(fd);raise r.ObservationError("GROWTH_RUNTIME_SHADOW")
 def config(self,role,path,raw,*,create=False,uid=0):
  self.check();parent,name=path.rsplit("/",1)
  directory=open_path(parent,directory=True,owners=(0,1100));fd=None
  try:
   before=identity(os.fstat(directory))
   flags=os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NOATIME|os.O_NONBLOCK
   if create:
    self.m.once("runtime_config_"+role)
    fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|flags,0o600,dir_fd=directory)
    os.fchown(fd,uid,uid);os.fchmod(fd,0o644);write_all(fd,raw,self.check);os.fsync(fd);os.close(fd);fd=None
   fd=os.open(name,os.O_RDONLY|flags,dir_fd=directory);info=os.fstat(fd)
   require(stat.S_ISREG(info.st_mode) and info.st_uid==info.st_gid==uid and stat.S_IMODE(info.st_mode)==0o644
 and info.st_nlink==1 and info.st_size==len(raw),"GROWTH_RUNTIME_CONFIG")
   require(read_fd(fd,8192,self.check)==raw and stable_identity(os.fstat(fd))==stable_identity(info)
 and identity(os.stat(name,dir_fd=directory,follow_symlinks=False))==identity(info)
 and identity(os.stat(parent,follow_symlinks=False))==before,"GROWTH_RUNTIME_CONFIG_DRIFT")
   self.report["configs"].append(dict(role=role,path=path,identity=list(identity(info)),bytes=len(raw),sha256=digest(raw),created=create))
   self.config_fds.append((path,fd,stable_identity(info)));fd=None
  finally:
   if fd is not None:os.close(fd)
   os.close(directory)
 def slice_config(self,role,*,user=False):
  row=self.binding["parents"][role];unit=row["unit"]
  prefixes=("/run/user/1100/systemd/user/","/etc/systemd/user/","/usr/lib/systemd/user/") if user else (
 "/etc/systemd/system/","/run/systemd/system/","/usr/lib/systemd/system/")
  found=[]
  for prefix in prefixes:
   self.absent(prefix+unit+".d")
   try:fd=open_path(prefix+unit,owners=(0,1100))
   except FileNotFoundError:continue
   os.close(fd);found.append(prefix+unit)
  require(len(found)<=1,"GROWTH_RUNTIME_CONFIG_SHADOW")
  if role not in ("ordinary","retained_ordinary"):
   require(found==["/etc/systemd/system/"+unit],"GROWTH_RUNTIME_ORIGINAL_CONFIG")
  if user:require(not found or found==[prefixes[0]+unit],"GROWTH_RUNTIME_USER_CONFIG")
  if found:self.config(role,found[0],runtime_config(row),uid=1100 if user else 0)
  return found[0] if found else None
 def user_directories(self):
  for path in ("/run/user/1100/systemd","/run/user/1100/systemd/user"):
   parent,name=path.rsplit("/",1);directory=open_path(parent,directory=True,owners=(0,1100))
   try:
    try:fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_NOATIME|os.O_CLOEXEC,dir_fd=directory)
    except FileNotFoundError:
     self.m.once("runtime_directory_"+name)
     os.mkdir(name,0o700,dir_fd=directory)
     fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_NOATIME|os.O_CLOEXEC,dir_fd=directory)
     os.fchown(fd,1100,1100);os.fchmod(fd,0o755)
     self.report["directories"].append(dict(path=path,identity=list(identity(os.fstat(fd)))))
    try:
     info=os.fstat(fd)
     require(info.st_uid==info.st_gid==1100 and stat.S_IMODE(info.st_mode) in (0o700,0o755)
 and identity(os.stat(path,follow_symlinks=False))==identity(info),"GROWTH_RUNTIME_DIRECTORY")
    finally:os.close(fd)
   finally:os.close(directory)
 def bus(self):
  fd=open_path("/run/user/1100",directory=True,owners=(0,1100))
  try:
   info=os.fstat(fd)
   require(info.st_uid==info.st_gid==1100 and stat.S_IMODE(info.st_mode)==0o700,"GROWTH_RUNTIME_USER_DIRECTORY")
   result=dict(runtime=list(identity(info)))
   for key,path in (("bus","bus"),("private","systemd/private")):
    if key=="private":
     parent=open_path("/run/user/1100/systemd",directory=True,owners=(0,1100))
     try:item=os.stat("private",dir_fd=parent,follow_symlinks=False)
     finally:os.close(parent)
    else:item=os.stat(path,dir_fd=fd,follow_symlinks=False)
    require(stat.S_ISSOCK(item.st_mode) and item.st_uid==item.st_gid==1100,"GROWTH_RUNTIME_SOCKET")
    result[key]=list(identity(item))
   return result
  finally:os.close(fd)
 def group(self,row):
  result=self.inventory.cgroup(row["control_group"])
  require(result["state"]=="UNPOPULATED","GROWTH_RUNTIME_GROUP")
  path="/sys/fs/cgroup"+row["control_group"]
  for name,expected in (("memory.max",str(row["memory_bytes"])),("memory.swap.max","0"),("pids.max",str(row["tasks_max"]))):
   require(read_kernel(path+"/"+name,64,self.check,expected_fs=0x63677270).decode().strip()==expected,"GROWTH_RUNTIME_KERNEL_LIMIT")
  cpu=read_kernel(path+"/cpu.max",128,self.check,expected_fs=0x63677270).decode().split()
  require(len(cpu)==2 and all(v.isdecimal() for v in cpu) and int(cpu[0])==int(cpu[1])>0,"GROWTH_RUNTIME_KERNEL_CPU")
  controllers=read_kernel(path+"/cgroup.controllers",256,self.check,expected_fs=0x63677270).decode().split()
  require({"cpu","memory","pids"}<=set(controllers),"GROWTH_RUNTIME_CONTROLLERS")
  require(result==self.inventory.cgroup(row["control_group"]),"GROWTH_RUNTIME_GROUP_DRIFT")
  return result
 def run(self):
  self.m.once("runtime_preparation");self.check()
  account=pwd.getpwuid(1100)
  require(dict(name=account.pw_name,uid=account.pw_uid,gid=account.pw_gid)==self.binding["account"],"GROWTH_RUNTIME_ACCOUNT_CHANGED")
  # Existing protections before any write/start, without opening a user bus.
  names=[item["name"] for item in self.description["expected_units"]]
  raw=self.command("guard_units",["show","--all","--property="+",".join(self.inventory.SHOW),"--",*names])
  units=self.inventory.show_many(names,raw=raw)
  for item in self.description["expected_units"]:self.inventory.quiet_service(item,units[item["name"]])
  for path in self.description["domain_cgroups"]:self.inventory.cgroup(path)
  self.inventory.processes();self.inventory.persistent();self.check()
  self.pool("/run")
  configs={role:self.slice_config(role) for role in RUNTIME_ROLES if role!="retained_ordinary"}
  manager=self.binding["manager"];drop="/etc/systemd/system/user@1100.service.d/50-local-hand-q2.conf"
  self.config("manager",drop,runtime_config(self.binding["parents"]["retained_ordinary"],manager=True))
  system={role:row for role,row in self.binding["parents"].items() if row["manager"]=="system"}
  manager_row=dict(self.binding["parents"]["retained_ordinary"],unit=manager["unit"],control_group=manager["control_group"])
  runtime_unit="user-runtime-dir@1100.service"
  names=[row["unit"] for row in system.values()]+[runtime_unit,manager["unit"]]
  before=self.show("system_before",names,missing=configs["ordinary"] is None)
  for role,row in system.items():
   value=before[row["unit"]];_runtime_properties(value,row,active=False)
   require(value["FragmentPath"]==(configs[role] or ""),"GROWTH_RUNTIME_FRAGMENT")
   if value["ActiveState"]=="active":self.group(row)
  def manager_check(value,active):
   _runtime_properties(value,manager_row,active=active,manager=True)
   require(value["FragmentPath"]==manager["fragment"] and value["DropInPaths"].split()==manager["dropins"],"GROWTH_RUNTIME_MANAGER_CONFIG")
  manager_check(before[manager["unit"]],False)
  runtime=before[runtime_unit]
  require(runtime["LoadState"]=="loaded" and runtime["Job"]=="" and runtime["ControlPID"]=="0"
 and (runtime["ActiveState"],runtime["SubState"]) in (("inactive","dead"),("active","exited"))
 and runtime["MainPID"]=="0" and not runtime["DropInPaths"]
 and runtime["FragmentPath"]=="/usr/lib/systemd/system/user-runtime-dir@.service","GROWTH_RUNTIME_DIR_SERVICE")
  # Fixed effective manager configuration files are protected before start.
  for path in [manager["fragment"],*manager["dropins"],runtime["FragmentPath"]]:
   fd=open_path(path)
   try:
    info=os.fstat(fd);require(stat.S_ISREG(info.st_mode) and info.st_uid==info.st_gid==0 and info.st_nlink==1,"GROWTH_RUNTIME_SYSTEM_CONFIG")
   finally:os.close(fd)
  if configs["ordinary"] is None:
   configs["ordinary"]="/run/systemd/system/"+system["ordinary"]["unit"]
   self.config("ordinary",configs["ordinary"],runtime_config(system["ordinary"]),create=True)
   self.command("system_reload",["daemon-reload"])
  starts=[name for name in names if before[name]["ActiveState"]=="inactive"]
  if starts:
   self.m.once("runtime_system_start");self.command("system_start",["start","--",*starts])
  after=self.show("system_after",names)
  manager_check(after[manager["unit"]],True);self.report["manager"]=after[manager["unit"]]
  require(after[runtime_unit]["ActiveState"]=="active" and after[runtime_unit]["SubState"]=="exited","GROWTH_RUNTIME_DIR_NOT_ACTIVE")
  for role,row in system.items():
   value=after[row["unit"]];_runtime_properties(value,row,active=True)
   require(value["FragmentPath"]==configs[role],"GROWTH_RUNTIME_FRAGMENT")
   self.report["parents"][role]=dict(properties=value,cgroup=self.group(row))
  self.report["bus"]=self.bus();self.pool("/run/user/1100")
  row=self.binding["parents"]["retained_ordinary"]
  found=self.slice_config("retained_ordinary",user=True)
  before=self.show("user_before",[row["unit"]],user=True,missing=found is None)[row["unit"]]
  _runtime_properties(before,row,active=False)
  require(before["FragmentPath"]==(found or ""),"GROWTH_RUNTIME_USER_FRAGMENT")
  if before["ActiveState"]=="active":self.group(row)
  if found is None:
   self.user_directories();found="/run/user/1100/systemd/user/"+row["unit"]
   self.config("retained_ordinary",found,runtime_config(row),create=True,uid=1100)
   self.command("user_reload",["daemon-reload"],user=True)
  if before["ActiveState"]=="inactive":
   self.m.once("runtime_user_start");self.command("user_start",["start","--",row["unit"]],user=True)
  value=self.show("user_after",[row["unit"]],user=True)[row["unit"]]
  _runtime_properties(value,row,active=True)
  require(value["FragmentPath"]==found and self.bus()==self.report["bus"],"GROWTH_RUNTIME_USER_DRIFT")
  self.report["parents"]["retained_ordinary"]=dict(properties=value,cgroup=self.group(row))
  for path,fd,expected in self.config_fds:
   require(stable_identity(os.fstat(fd))==stable_identity(os.stat(path,follow_symlinks=False))==expected,"GROWTH_RUNTIME_CONFIG_DRIFT")
  for fd,pool in self.pool_fds.values():
   size=os.fstatvfs(fd);pool["after"]=[size.f_bavail*size.f_frsize,size.f_favail]
  self.check()
  return validate_runtime_report(self.report,self.description,self.report["boot_id"],self.description["phase"])
 def close(self):
  for _,fd,_ in self.config_fds:os.close(fd)
  for fd,_ in self.pool_fds.values():os.close(fd)
class GuestMaintenance:
 """Single-process, two-phase helper. No generic command or recovery API."""
 def __init__(self, description, *, window=None):
  self.description=description
  self.window=window or GuestWindow(description["window_seconds"], description["change_seconds"])
  self.observation=None
  self.device=None
  self.active_command=None
  self.inventory=None
  self.runtime=None
  self.stage="IDENTITY"
  self.started=set()
 def once(self, action):
  require(action not in self.started, "GROWTH_GUEST_NO_RETRY")
  self.window.check(change=True)
  self.started.add(action)
 def sample(self):
  if self.observation is not None:
   self.observation.close()
  self.observation=r.Observation(self.description["paths"], self.window.check)
  return self.observation.collect()
 def journal_tree(self):
  require(self.observation is not None, "GROWTH_JOURNAL_PARENT_REQUIRED")
  path=self.description["paths"]["journal"]
  fd=self.observation.held[tuple(r.path_value(path))][0]
  def mount(fd):
   return r.mount_id(r.kernel_read("/proc/self/fdinfo/" + str(fd), 4096, self.window.check))
  return tree_digest(fd, self.window.check, mount_id=mount)
 def observe_device(self, rows, size):
  if self.device is not None:
   self.device.close()
  self.device=JournalDevice(rows[3], self.description["journal_serial"], size, self.window.check)
  return self.device.report()
 def pre(self, *, output=emit, receive=receive_token):
  self.stage="PRE_IDENTITY"
  current_boot=boot_id(self.window.check)
  require(current_boot == self.description["original_boot_id"], "GROWTH_ORIGINAL_BOOT")
  rows=self.sample()
  same_parents(self.description["saved_rows"], rows)
  device=self.observe_device(rows, OLD_SIZE)
  inventory=GuestInventory(self.description, self.window.check)
  self.inventory=inventory
  self.stage="PRE_RUNTIME_PREPARATION"
  self.runtime=RuntimePreparation(self,current_boot)
  runtime=self.runtime.run()
  self.stage="PRE_QUIESCENCE"
  quiet=inventory.collect()
  self.stage="PRE_TOOL"
  tool=tool_binding("/usr/sbin/resize2fs", self.window.check, version=True)
  self.stage="PRE_TREE"
  tree=self.journal_tree()
  self.observation.reopen()
  self.device.recheck()
  require(boot_id(self.window.check) == current_boot, "GROWTH_BOOT_DRIFT")
  report=dict(schema=REPORT_SCHEMA, session=SESSION, phase="pre", status="GUEST_QUIET",
 guest_startup_assurance=validate_startup_assurance(self.description.get("guest_startup_assurance")),
 nonce=self.description["nonce"], source_binding_sha256=self.description["source_binding_sha256"],
 boot_id=current_boot, rows=rows, tree=tree, journal_device=device,
 resize2fs=tool, quiescence=quiet, runtime_preparation=runtime, resource_observation=resource_observation())
  validate_pre_report(report, self.description)
  self.stage="WAIT_HOST_DURABLE_PRE_REPORT"
  output(report)
  report_sha=digest(canonical(report))
  receive(continue_token(self.description["nonce"], report_sha), self.window.check)
  self.stage="PRE_FINAL_QUIESCENCE"
  inventory.collect()
  self.observation.reopen()
  self.device.recheck()
  require(boot_id(self.window.check) == current_boot, "GROWTH_BOOT_DRIFT")
  self.once("poweroff")
  self.stage="POWER_OFF_REQUESTED"
  output(dict(schema=REPORT_SCHEMA, session=SESSION, status="POWER_OFF_REQUESTED",
 nonce=self.description["nonce"], pre_report_sha256=report_sha,
 guest_startup_assurance=validate_startup_assurance(self.description.get("guest_startup_assurance"))))
  self.active_command=bound_command(inventory.systemctl,
 ["--system", "--no-pager", "--no-ask-password", "poweroff"], self.window.check, limit=8192)
  result=self.active_command.collect()
  require(result["returncode"] == 0 and result["both_eof"], "GROWTH_POWEROFF_FAILED")
  return report
 def post(self, *, output=emit):
  self.stage="POST_PRE_REPORT_BINDING"
  before=validate_pre_report(self.description["pre_report"], self.description)
  require(digest(canonical(before)) == self.description["pre_report_sha256"], "GROWTH_PRE_REPORT_DIGEST")
  current_boot=boot_id(self.window.check)
  require(current_boot != before["boot_id"], "GROWTH_NEW_BOOT_REQUIRED")
  rows=self.sample()
  same_parents(before["rows"], rows)
  device=self.observe_device(rows, NEW_SIZE)
  require(all(device[key] == before["journal_device"][key] for key in ("uuid", "serial", "node"))
 and device["superblock"]["features"] == before["journal_device"]["superblock"]["features"]
 and device["superblock"]["block_size"] == before["journal_device"]["superblock"]["block_size"]
 and device["superblock"]["filesystem_bytes"] == before["journal_device"]["superblock"]["filesystem_bytes"],
 "GROWTH_POST_DEVICE_CHANGED")
  inventory=GuestInventory(self.description, self.window.check)
  self.inventory=inventory
  self.stage="POST_RUNTIME_PREPARATION"
  self.runtime=RuntimePreparation(self,current_boot)
  runtime=self.runtime.run()
  self.stage="POST_QUIESCENCE"
  inventory.collect()
  self.stage="POST_TOOL"
  verify_tool(before["resize2fs"], self.window.check)
  self.observation.reopen()
  self.device.recheck()
  self.once("resize2fs")
  self.stage="RESIZE2FS_STARTED"
  self.active_command=bound_command(before["resize2fs"], [self.device.path], self.window.check)
  result=self.active_command.collect()
  require(result["returncode"] == 0 and result["both_eof"], "GROWTH_RESIZE2FS_FAILED")
  self.stage="POST_TREE"
  self.device.recheck()
  final_superblock=self.device.read_superblock()
  require(final_superblock["filesystem_bytes"] == NEW_SIZE and
 all(final_superblock[key] == device["superblock"][key] for key in ("uuid", "features", "block_size")),
 "GROWTH_EXT4_FINAL_SIZE")
  self.device.superblock=final_superblock
  tree=self.journal_tree()
  verify_preservation(before["tree"], tree)
  self.stage="POST_CAPACITY"
  final_rows=self.sample()
  validate_completion(before["rows"], final_rows)
  self.stage="POST_FINAL_QUIESCENCE"
  quiet=inventory.collect()
  require(boot_id(self.window.check) == current_boot, "GROWTH_BOOT_DRIFT")
  report=dict(schema=REPORT_SCHEMA, session=SESSION, phase="post", status="FILESYSTEM_GROWN",
 guest_startup_assurance=validate_startup_assurance(self.description.get("guest_startup_assurance")),
 nonce=self.description["nonce"], source_binding_sha256=self.description["source_binding_sha256"],
 boot_id=current_boot, original_boot_id=before["boot_id"],
 pre_report_sha256=self.description["pre_report_sha256"], rows=final_rows, tree=tree,
 journal_device=self.device.report(), resize2fs=before["resize2fs"], quiescence=quiet,runtime_preparation=runtime,
 resource_observation=resource_observation(),
 resize_result=dict(returncode=result["returncode"], both_eof=result["both_eof"],
 stdout_bytes=len(result["stdout"]), stderr_bytes=len(result["stderr"]),
 stdout_sha256=digest(result["stdout"]), stderr_sha256=digest(result["stderr"])))
  self.window.check()
  validate_post_report(report, self.description)
  output(report)
  return report
 def failure(self, error):
  process=self.active_command.process if self.active_command else None
  code=str(error) if isinstance(error, r.ObservationError) else "GROWTH_GUEST_IO_OR_RUNTIME"
  require(re.fullmatch(r"[A-Z0-9_]{1,128}", code), "GROWTH_ERROR_CODE")
  diagnostic=dict(errno=getattr(error,"errno",None),error_type=type(error).__name__,
 context=dict(getattr(self.inventory,"context",{})))
  if hasattr(error,"path_diagnostic"):diagnostic["path_lookup"]=dict(error.path_diagnostic)
  if self.runtime is not None:diagnostic["runtime_preparation"]=self.runtime.report
  serial=getattr(error,"serial_diagnostic",None)
  if code=="GROWTH_JOURNAL_SERIAL" and type(serial) is dict and set(serial)=={
 "expected_bytes","actual_bytes","expected_hex","actual_hex"} and all(
 type(serial[name+"_bytes"]) is int and 0<=serial[name+"_bytes"]<=limit and
 type(serial[name+"_hex"]) is str and len(serial[name+"_hex"])==2*serial[name+"_bytes"] and
 re.fullmatch(r"[0-9a-f]*",serial[name+"_hex"]) is not None
 for name,limit in (("expected",20),("actual",128))):
   diagnostic["serial"]=dict(serial)
  return dict(schema=REPORT_SCHEMA, session=SESSION, phase=self.description["phase"], status="INCOMPLETE",
 nonce=self.description["nonce"],source_binding_sha256=self.description["source_binding_sha256"],
 stage=self.stage, reason=code, actions_started=sorted(self.started),
 guest_startup_assurance=validate_startup_assurance(self.description.get("guest_startup_assurance")),
 process_pid=process.pid if process else None,
 process_returncode=process.poll() if process else None,
 diagnostic=diagnostic,
 resource_observation=resource_observation(),
 process_exit="UNKNOWN" if process and process.poll() is None else "OBSERVED_OR_NOT_STARTED")
 def close(self):
  if self.runtime is not None:self.runtime.close()
  if self.observation is not None:
   self.observation.close()
  if self.device is not None:
   self.device.close()
  if self.active_command is not None:
   self.active_command.close()
def entry(raw):
 maintenance=None
 try:
  require(os.geteuid() == 0, "GROWTH_GUEST_EUID")
  require(all(resource.getrlimit(key) == (resource.RLIM_INFINITY, resource.RLIM_INFINITY)
 for key in (resource.RLIMIT_CPU, resource.RLIMIT_FSIZE)), "GROWTH_INHERITED_MUTATOR_LIMIT")
  description=descriptor(raw)
  for key, maximum in ((resource.RLIMIT_AS, 256 * 1048576), (resource.RLIMIT_NOFILE, 128),
 (resource.RLIMIT_CORE, 0)):
   resource.setrlimit(key, (maximum, maximum))
  maintenance=GuestMaintenance(description)
  if description["phase"] == "pre":
   maintenance.pre()
  else:
   require(os.read(0, 1) == b"", "GROWTH_POST_STDIN")
   maintenance.post()
  return 0
 except (Exception, KeyboardInterrupt) as error:
  try:
   emit(maintenance.failure(error) if maintenance else
 dict(schema=REPORT_SCHEMA, session=SESSION, status="INCOMPLETE", stage="DESCRIPTION",
 guest_startup_assurance=None,
 reason=str(error) if isinstance(error, r.ObservationError) else "GROWTH_GUEST_IO_OR_RUNTIME"), 2)
  except (OSError, r.ObservationError):
   pass
  return 3
 finally:
  if maintenance is not None:
   maintenance.close()
def main():
 try:
  require(len(sys.argv) == 3, "GROWTH_GUEST_ARGUMENTS")
  raw=base64.b64decode(sys.argv[1], validate=True)
  require(digest(raw) == sha_value(sys.argv[2]), "GROWTH_GUEST_DESCRIPTION_DIGEST")
  return entry(raw)
 except Exception:
  return 3
if __name__ == "__main__":
 sys.exit(main())

class ProcessIdentity:
 def __init__(self, pid, argv, tool_fd, check):
  require(type(pid) is int and pid > 1 and hasattr(os, "pidfd_open"), "GROWTH_PID")
  self.pid, self.argv, self.tool_fd, self.check=pid, argv, tool_fd, check
  self.fd=os.pidfd_open(pid, 0)
  self.start=None
  try:
   self.recheck()
  except BaseException:
   self.close()
   raise
 def exited(self):
  self.check()
  return bool(select.select([self.fd], [], [], 0)[0])
 def recheck(self):
  require(not self.exited(), "GROWTH_PROCESS_EXITED")
  start=proc_start(proc_bytes(self.pid, "stat", 16384, self.check))
  require(self.start in (None, start), "GROWTH_PID_REUSED")
  self.start=start
  expected=b"\0".join(os.fsencode(word) for word in self.argv) + b"\0"
  require(proc_bytes(self.pid, "cmdline", 65536, self.check) == expected, "GROWTH_PROCESS_ARGV")
  exe=os.open(f"/proc/{self.pid}/exe", os.O_PATH | os.O_CLOEXEC)
  try:
   require(identity(os.fstat(exe)) == identity(os.fstat(self.tool_fd)), "GROWTH_PROCESS_EXE")
  finally:
   os.close(exe)
  require(proc_start(proc_bytes(self.pid, "stat", 16384, self.check)) == start and not self.exited(),
 "GROWTH_PROCESS_DRIFT")
  return dict(pid=self.pid, starttime=start, argv_sha256=digest(expected))
 def close(self):
  os.close(self.fd)
