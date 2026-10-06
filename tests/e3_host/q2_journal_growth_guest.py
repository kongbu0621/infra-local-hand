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
import struct
import subprocess
import sys
import time
import pwd
from e3_host import q2_core_capacity_reader as r
require, canonical, digest=r.require, r.canonical, r.digest
MAX_BYTES, MAX_ENTRIES=268435456, 32768
SESSION="lhqjgrow-20261006a"
SCHEMA="lhq-journal-growth-input/v1"
REPORT_SCHEMA="lhq-journal-growth-guest/v1"
OLD_SIZE, NEW_SIZE=268435456, 536870912
STREAM_LIMIT=1048576
ENVIRONMENT={"HOME": "/root", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
 "LANG": "C", "LC_ALL": "C", "SYSTEMD_COLORS": "0",
 "SYSTEMD_PAGER": "cat"}
UNIT_PATTERN=re.compile(r"[A-Za-z0-9_.:@\\x-]{1,240}\.(?:service|scope|slice|socket|timer|path|target)")
def terminal_binding(expected=None):
 try:
  s=os.fstat(0); value=dict(mode="terminal",sid=os.getsid(0),dev=s.st_dev,ino=s.st_ino,
  rdev=s.st_rdev,uid=s.st_uid,gid=s.st_gid,perm=stat.S_IMODE(s.st_mode))
  foreground=os.isatty(0) and stat.S_ISCHR(s.st_mode) and os.tcgetpgrp(0)==os.getpgrp()
 except (OSError,AttributeError) as error:
  raise r.ObservationError("GROWTH_TERMINAL_REQUIRED") from error
 require(foreground,"GROWTH_TERMINAL_FOREGROUND")
 require(expected is None or value==expected,"GROWTH_TERMINAL_DRIFT")
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
 value=dict(schema="lhq-journal-growth-input/v1", session=SESSION, phase=phase, nonce=nonce,
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
def writer_request(raw):
 def pairs(items):
  result={}
  for key, value in items:
   require(key not in result, "GROWTH_WRITER_DUPLICATE")
   result[key]=value
  return result
 require(type(raw) is bytes and len(raw) <= 65536, "GROWTH_WRITER_INPUT")
 value=json.loads(raw, object_pairs_hook=pairs)
 require(type(value) is dict and set(value) == {"schema", "scope", "session", "D", "nonce",
 "images", "origins", "boot_id", "checkpoint", "started"}, "GROWTH_WRITER_INPUT")
 require(value["schema"] == "lhq-journal-writer/v1" and value["scope"] ==
 "LH-Q2-CORE-JOURNAL-HOST-READ-v1" and value["session"] == "lhqjgrow-20261006a",
 "GROWTH_WRITER_SCOPE")
 require(type(value["D"]) is str and re.fullmatch("[0-9a-f]{40}", value["D"])
 and type(value["nonce"]) is str and re.fullmatch("[0-9a-f]{64}", value["nonce"]), "GROWTH_WRITER_BINDING")
 require(type(value["boot_id"]) is str and re.fullmatch(
 r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value["boot_id"]), "GROWTH_WRITER_BOOT")
 for field in ("origins", "started"):
  require(type(value[field]) is list and len(value[field]) == 2 and
 all(type(n) is int and n >= 0 for n in value[field]), "GROWTH_WRITER_CLOCK")
 require(type(value["checkpoint"]) is int and 1 <= value["checkpoint"] <= 8, "GROWTH_WRITER_COUNT")
 images=value["images"]
 require(type(images) is dict and set(images) == {"system", "quota", "journal", "evidence", "seed"}
 and all(type(pair) is list and len(pair) == 2 and all(type(n) is int and n > 0 for n in pair)
 for pair in images.values()) and len(set(map(tuple, images.values()))) == 5, "GROWTH_WRITER_IMAGES")
 return value
def writer_payload(host, guest, kernel, commit):
 import ast
 def functions(raw, names):
  source=raw.decode("utf-8")
  nodes={node.name: node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
  return "\n\n".join(ast.get_source_segment(source, nodes[name]) for name in names) + "\n"
 prefix="""import json,re,time,resource,types,base64
class WriterError(RuntimeError): pass
def require(ok, code):
 if not ok: raise WriterError(code)
prior=types.SimpleNamespace(r=types.SimpleNamespace(ObservationError=WriterError))
MIB=1048576
"""
 payload=kernel.decode("utf-8") + "\n" + prefix
 payload += functions(guest, ("identity", "proc_start", "writer_request"))
 payload += functions(host, ("_proc_limit", "_bounded_names", "_proc_read", "_fd_snapshot", "collect_image_writers"))
 payload += "\nEXECUTION_D=" + repr(commit) + "\n" + WRITER_ENTRY
 raw=payload.encode("utf-8")
 require(len(raw) <= 32768, "GROWTH_WRITER_SOURCE_LIMIT")
 return raw
WRITER_LOADER="""import base64,hashlib,sys
p=base64.b64decode(sys.argv[1],validate=True)
if not 0<len(p)<=32768 or hashlib.sha256(p).hexdigest()!=sys.argv[2]: raise ValueError('WRITER_SOURCE_PIN')
exec(compile(p,'<fixed-writer-observer>','exec'),{'__name__':'__main__'})
"""
WRITER_ENTRY="""
def writer_entry():
 request=None
 try:
  require(os.geteuid()==0, 'GROWTH_WRITER_UID')
  for kind,cap in ((resource.RLIMIT_AS,268435456),(resource.RLIMIT_NOFILE,128),(resource.RLIMIT_CORE,0)):
   resource.setrlimit(kind,(cap,cap))
  request=writer_request(base64.b64decode(sys.argv[3],validate=True))
  require(request['D']==EXECUTION_D, 'GROWTH_WRITER_D')
  previous=list(request['started'])
  def check():
   now=[time.clock_gettime_ns(c) for c in (time.CLOCK_MONOTONIC,time.CLOCK_BOOTTIME)]
   require(all(o<=s<=p<=n<min(o+900000000000,s+15000000000)
    for o,s,p,n in zip(request['origins'],request['started'],previous,now)), 'GROWTH_WRITER_DEADLINE')
   previous[:]=now
  check()
  boot=read_fact('boot',check,{})
  require(boot==(request['boot_id']+'\\n').encode('ascii'), 'GROWTH_WRITER_BOOT')
  rows=collect_image_writers({k:tuple(v) for k,v in request['images'].items()},check,
   mount_reader=lambda:read_fact('mountinfo',check,{}))
  check()
  usage=resource.getrusage(resource.RUSAGE_SELF)
  result=dict(schema='lhq-journal-writer-result/v1',request=request,complete=True,
   rows=[row for row in rows if row['writable_images']],
   usage=dict(cpu_us=int((usage.ru_utime+usage.ru_stime)*1000000),peak_rss_bytes=usage.ru_maxrss*1024))
 except Exception as error:
  cause=error.__cause__
  known=cause if isinstance(cause,(WriterError,KernelFactError)) else error
  result=dict(schema='lhq-journal-writer-result/v1',request=request,complete=False,
   reason=str(known) if isinstance(known,(WriterError,KernelFactError)) else 'GROWTH_WRITER_IO',
   errno=getattr(error,'errno',None) or getattr(cause,'errno',None))
 raw=json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()+b'\\n'
 require(len(raw)<=65536,'GROWTH_WRITER_OUTPUT')
 sys.stdout.buffer.write(raw); sys.stdout.buffer.flush()
 return 0 if result['complete'] else 3
sys.exit(writer_entry())
"""
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
def descriptor(raw):
 value=r.parse(raw, 65536)
 keys={"schema", "session", "phase", "nonce", "source_binding_sha256", "paths", "saved_rows",
 "original_boot_id", "journal_serial", "expected_units", "domain_cgroups", "domain_units",
 "protected_roots", "essential_paths", "window_seconds", "change_seconds"}
 require(type(value) is dict and value.get("phase") in ("pre", "post"), "GROWTH_DESCRIPTION")
 if value["phase"] == "post":
  keys |= {"pre_report", "pre_report_sha256"}
 require(set(value) == keys and value["schema"] == SCHEMA and value["session"] == SESSION,
 "GROWTH_DESCRIPTION")
 sha_value(value["nonce"]); sha_value(value["source_binding_sha256"])
 uuid_value(value["original_boot_id"])
 require(type(value["journal_serial"]) is str and
 re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value["journal_serial"]), "GROWTH_SERIAL")
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
def open_path(path, *, directory=False, writable=False, block=False, owners=(0,)):
 """Walk protected ancestors by fd; no symlink or weak atime fallback."""
 parts=r.path_value(path)
 current=os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC)
 try:
  r.qualify(os.fstat(current))
  for index, name in enumerate(parts):
   last=index == len(parts) - 1
   flags=(os.O_RDWR if writable and last else os.O_RDONLY) | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NOATIME | os.O_NONBLOCK
   if not last or directory:
    flags |= os.O_DIRECTORY
   next_fd=os.open(name, flags, dir_fd=current)
   os.close(current)
   current=next_fd
   info=os.fstat(current)
   if not last:
    require(stat.S_ISDIR(info.st_mode) and info.st_uid in owners and not info.st_mode & 0o022,
 "GROWTH_PATH_ANCESTOR")
   else:
    require(info.st_uid in owners and not info.st_mode & (0o002 if block else 0o022), "GROWTH_PATH_PROTECTION")
    if block:
     require(stat.S_ISBLK(info.st_mode), "GROWTH_BLOCK_TYPE")
  result, current=current, None
  return result
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
   require(observed_serial == serial.encode("ascii") + b"\n", "GROWTH_JOURNAL_SERIAL")
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
 SHOW=("Id", "LoadState", "ActiveState", "SubState", "MainPID", "ControlPID", "ControlGroup",
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
 def ctl(self, arguments, *, user_uid=None):
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
  require(result["returncode"] == 0 and result["both_eof"] and not result["stderr"], "GROWTH_SYSTEMCTL_STDERR")
  if bus is not None:
   require(r.identity(os.stat("/run/user/1100/bus", follow_symlinks=False)) == bus,
 "GROWTH_USER_BUS_DRIFT")
  verify_tool(self.systemctl, self.check)
  return result["stdout"]
 def show_many(self, names, *, user_uid=None):
  require(0 < len(names) <= 128 and len(names) == len(set(names)) and
 all(type(name) is str and UNIT_PATTERN.fullmatch(name) for name in names), "GROWTH_UNIT_NAME")
  raw=self.ctl(["show", "--all", "--property=" + ",".join(self.SHOW), *names], user_uid=user_uid)
  result={}
  for block in raw.decode("utf-8", "strict").strip().split("\n\n"):
   entries=[line.split("=", 1) for line in block.splitlines()]
   require(all(len(item) == 2 for item in entries) and len(entries) == len({item[0] for item in entries}),
 "GROWTH_SYSTEMCTL_FORMAT")
   value=dict(entries)
   require(set(value) <= set(self.SHOW) and {"Id", "LoadState", "ActiveState", "SubState"} <= set(value)
 and value["Id"] in names and value["Id"] not in result, "GROWTH_SYSTEMCTL_FIELDS")
   if value["Id"].endswith(".service") and value["LoadState"] == "loaded":
    require({"MainPID", "ControlPID", "Restart"} <= set(value), "GROWTH_SERVICE_FIELDS")
   result[value["Id"]]={key: value.get(key, "") for key in self.SHOW}
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
 def quiet_service(self, expected):
  value=self.show(expected["name"])
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
 def processes(self):
  rows, total_fds=[], 0
  names=sorted(name for name in os.listdir("/proc") if name.isdecimal())
  require(len(names) <= 2048, "GROWTH_PROCESS_COUNT")
  self_pid=os.getpid()
  for name in names:
   self.check()
   prefix="/proc/" + name
   try:
    start_raw=read_kernel(prefix + "/stat", 4096, self.check, expected_fs=0x9FA0)
    start=process_start(start_raw)
    cmdline=read_kernel(prefix + "/cmdline", 65536, self.check, expected_fs=0x9FA0)
    cgroup=read_kernel(prefix + "/cgroup", 4096, self.check, expected_fs=0x9FA0)
    if int(name) != self_pid:
     require(not any(root.encode() in cmdline for root in self.roots), "GROWTH_BUSINESS_PROCESS")
     for link in ("exe", "cwd"):
      try:
       target=os.readlink(prefix + "/" + link)
      except FileNotFoundError:
       require(not cmdline, "GROWTH_PROCESS_LINK_UNKNOWN")
       continue
      require(not under(target.removesuffix(" (deleted)"), self.roots), "GROWTH_BUSINESS_PROCESS")
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
    maps=read_kernel(prefix + "/maps", 1048576, self.check, expected_fs=0x9FA0)
    for line in maps.splitlines():
     fields=line.split(None, 5)
     if len(fields) == 6 and fields[1][1:2] == b"w" and fields[1][3:4] == b"s":
      mapped=os.fsdecode(fields[5]).removesuffix(" (deleted)")
      require(not under(mapped, self.roots), "GROWTH_MAPPED_WRITER")
    require(process_start(read_kernel(prefix + "/stat", 4096, self.check, expected_fs=0x9FA0)) == start,
 "GROWTH_PROCESS_REUSE")
    rows.append(dict(pid=int(name), start=start, cgroup_sha256=digest(cgroup)))
   except FileNotFoundError as error:
    raise r.ObservationError("GROWTH_PROCESS_INVENTORY_DRIFT") from error
  after=sorted(name for name in os.listdir("/proc") if name.isdecimal())
  require(names == after, "GROWTH_PROCESS_INVENTORY_DRIFT")
  return dict(processes=len(rows), fd_count=total_fds, sha256=digest(canonical(rows)))
 def startup_manager(self, *, user_uid=None):
  expected={row["name"] for row in self.description["expected_units"]}
  domain_names={row["name"] for row in self.description["domain_units"]}
  names=set()
  kinds="--type=service,scope,slice,socket,timer,path,target"
  for arguments in (["list-units", "--all", "--plain", "--no-legend", kinds],
 ["list-unit-files", "--no-legend", kinds]):
   for line in self.ctl(arguments, user_uid=user_uid).decode("utf-8", "strict").splitlines():
    fields=line.split()
    require(fields and UNIT_PATTERN.fullmatch(fields[0]), "GROWTH_UNIT_LIST")
    names.add(fields[0])
    require(len(names) <= 2048, "GROWTH_UNIT_COUNT")
  related, observed=[], {}
  ordered=sorted(names)
  for offset in range(0, len(ordered), 128):
   observed.update(self.show_many(ordered[offset:offset + 128], user_uid=user_uid))
  for name in ordered:
   self.check()
   self.context=dict(manager="user_1100" if user_uid else "system", unit=name)
   value=observed[name]
   flat=canonical(value)
   match=name in expected or any(root.encode() in flat for root in self.roots)
   if match and name not in domain_names:
    require(name in expected, "GROWTH_UNDECLARED_BUSINESS_UNIT")
    related.append(self.quiet_service(next(row for row in self.description["expected_units"]
 if row["name"] == name)))
   enabled=value["UnitFileState"] in ("enabled", "enabled-runtime", "linked", "linked-runtime", "generated")
   if enabled and name not in expected and name not in domain_names:
    actions=" ".join(value[key] for key in self.SHOW if key.startswith("Exec"))
    indirect=re.search(r"(?:/|\s)(?:ba|da)?sh(?:\s|;|$)|/python[0-9.]*(?:\s|;)|/perl(?:\s|;)|"
 r"/(?:cron|crond|atd|run-parts|systemd-run)(?:\s|;|$)", actions)
    if indirect:
     self.context["action_kind"]=indirect.group(0).strip(" /;")
     raise r.ObservationError("GROWTH_INDIRECT_STARTUP_UNVERIFIED")
  domains=[]
  for item in self.description["domain_units"]:
   if (item["manager"] == "user") != (user_uid is not None):
    continue
   value=observed.get(item["name"])
   if value is None:
    value=self.show_many([item["name"]], user_uid=user_uid)[item["name"]]
   require(value["LoadState"] in ("loaded", "not-found") and
 value["ControlGroup"] in ("", item["control_group"]), "GROWTH_DOMAIN_UNIT")
   require(item["name"].endswith(".slice") and not any(value[key] for key in self.SHOW if key.startswith("Exec")),
 "GROWTH_DOMAIN_UNIT_ACTION")
   domains.append(dict(name=item["name"], properties_sha256=digest(canonical(value))))
  return dict(unit_count=len(names), related=related, domains=domains, indirect_startup="CLASSIFIED")
 def startup(self):
  result={"system": self.startup_manager()}
  if any(item["manager"] == "user" for item in self.description["domain_units"]):
   result["user_1100"]=self.startup_manager(user_uid=1100)
  return result
 def persistent(self):
  mounts=r.mounts(r.kernel_read("/proc/self/mountinfo", 1048576, self.check))
  records=[]
  for path in self.description["essential_paths"]:
   self.check()
   fd=open_path(path, owners=(0, 1100))
   try:
    info=os.fstat(fd)
    require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), "GROWTH_ESSENTIAL_OBJECT")
    mid=r.mount_id(r.kernel_read("/proc/self/fdinfo/" + str(fd), 4096, self.check))
    require(mid in mounts, "GROWTH_ESSENTIAL_MOUNT")
    filesystem=dict(mount=mounts[mid], uuid=r.fs_uuid(fd))
    validate_durable_filesystem(filesystem)
    require(filesystem["mount"]["device"] == info.st_dev, "GROWTH_ESSENTIAL_DEVICE")
    records.append(dict(path_sha256=digest(path.encode()), filesystem_uuid=filesystem["uuid"],
 identity=r.identity(info)))
   finally:
    os.close(fd)
  return dict(count=len(records), sha256=digest(canonical(records)))
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
PRE_FIELDS={"schema", "session", "phase", "status", "nonce", "source_binding_sha256", "boot_id",
 "rows", "tree", "journal_device", "resize2fs", "quiescence", "resource_observation"}
def validate_pre_report(value, description):
 require(type(value) is dict and set(value) == PRE_FIELDS and value["schema"] == REPORT_SCHEMA
 and value["session"] == SESSION and value["phase"] == "pre" and value["status"] == "GUEST_QUIET"
 and value["nonce"] == description["nonce"]
 and value["source_binding_sha256"] == description["source_binding_sha256"]
 and value["boot_id"] == description["original_boot_id"], "GROWTH_PRE_REPORT")
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
class GuestMaintenance:
 """Single-process, two-phase helper. No generic command or recovery API."""
 def __init__(self, description, *, window=None):
  self.description=description
  self.window=window or GuestWindow(description["window_seconds"], description["change_seconds"])
  self.observation=None
  self.device=None
  self.active_command=None
  self.inventory=None
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
  self.stage="PRE_QUIESCENCE"
  inventory=GuestInventory(self.description, self.window.check)
  self.inventory=inventory
  quiet=inventory.collect()
  self.stage="PRE_TOOL"
  tool=tool_binding("/usr/sbin/resize2fs", self.window.check, version=True)
  self.stage="PRE_TREE"
  tree=self.journal_tree()
  self.observation.reopen()
  self.device.recheck()
  require(boot_id(self.window.check) == current_boot, "GROWTH_BOOT_DRIFT")
  report=dict(schema=REPORT_SCHEMA, session=SESSION, phase="pre", status="GUEST_QUIET",
 nonce=self.description["nonce"], source_binding_sha256=self.description["source_binding_sha256"],
 boot_id=current_boot, rows=rows, tree=tree, journal_device=device,
 resize2fs=tool, quiescence=quiet, resource_observation=resource_observation())
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
 nonce=self.description["nonce"], pre_report_sha256=report_sha))
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
  self.stage="POST_QUIESCENCE"
  inventory=GuestInventory(self.description, self.window.check)
  self.inventory=inventory
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
 nonce=self.description["nonce"], source_binding_sha256=self.description["source_binding_sha256"],
 boot_id=current_boot, original_boot_id=before["boot_id"],
 pre_report_sha256=self.description["pre_report_sha256"], rows=final_rows, tree=tree,
 journal_device=self.device.report(), resize2fs=before["resize2fs"], quiescence=quiet,
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
  return dict(schema=REPORT_SCHEMA, session=SESSION, phase=self.description["phase"], status="INCOMPLETE",
 stage=self.stage, reason=code, actions_started=sorted(self.started),
 process_pid=process.pid if process else None,
 process_returncode=process.poll() if process else None,
 diagnostic=dict(errno=getattr(error, "errno", None),
 context=getattr(self.inventory, "context", {})),
 resource_observation=resource_observation(),
 process_exit="UNKNOWN" if process and process.poll() is None else "OBSERVED_OR_NOT_STARTED")
 def close(self):
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

def writer_failure(raw, request):
 try:
  value=r.parse(raw,65536)
  require(type(value) is dict and set(value)=={"schema","request","complete","reason","errno"}
 and value["schema"]=="lhq-journal-writer-result/v1" and value["complete"] is False
 and (value["request"] is None or canonical(value["request"])==canonical(request))
 and type(value["reason"]) is str and re.fullmatch("[A-Z0-9_]{1,160}",value["reason"])
 and (value["errno"] is None or type(value["errno"]) is int and 0<=value["errno"]<=4095),
 "GROWTH_WRITER_FAILURE_REPORT")
  return {key:value[key] for key in ("reason","errno")}
 except (ValueError,RuntimeError,TypeError):
  raise r.ObservationError("GROWTH_WRITER_FAILURE_REPORT") from None
class WriterProtocol:
 def validate(self, report, request, checkpoint):
  require(type(report) is dict and set(report) == {"schema", "request", "complete", "rows", "usage"}
 and report["schema"] == "lhq-journal-writer-result/v1" and report["complete"] is True
 and report["request"] == request, "GROWTH_WRITER_REPORT")
  require(request["D"] == self.commit and request["nonce"] == self.nonce and request["images"] == self.images
 and request["checkpoint"] == checkpoint and request["boot_id"] == self.window.binding["boot_id"]
 and request["origins"] == self.window.binding["origins"], "GROWTH_WRITER_REPORT_BINDING")
  now=[time.clock_gettime_ns(c) for c in (time.CLOCK_MONOTONIC, time.CLOCK_BOOTTIME)]
  require(all(o <= s <= n for o, s, n in zip(request["origins"], request["started"], now)), "GROWTH_WRITER_CLOCK")
  rows=report["rows"]
  require(type(rows) is list and len(rows) <= 32768, "GROWTH_WRITER_ROWS")
  seen=set()
  for row in rows:
   require(type(row) is dict and set(row) == {"pid", "starttime", "complete", "writable_images"}
 and type(row["pid"]) is int and row["pid"] > 0 and row["pid"] not in seen
 and type(row["starttime"]) is int and row["starttime"] >= 0 and row["complete"] is True
 and type(row["writable_images"]) is list and row["writable_images"]
 and all(type(v) is str and v in self.images for v in row["writable_images"])
 and len(set(row["writable_images"])) == len(row["writable_images"]), "GROWTH_WRITER_ROWS")
   seen.add(row["pid"])
  require(type(report["usage"]) is dict and set(report["usage"]) == {"cpu_us", "peak_rss_bytes"}
 and all(type(n) is int and n >= 0 for n in report["usage"].values()), "GROWTH_WRITER_USAGE")
 def observe(self, images, check):
  require(not self.failed and len(self.reports) < 8 and images == {k: tuple(v) for k, v in self.images.items()},
 "GROWTH_WRITER_NO_RETRY")
  self.failed=True
  checkpoint=len(self.reports) + 1
  request=dict(schema="lhq-journal-writer/v1", scope="LH-Q2-CORE-JOURNAL-HOST-READ-v1",
 session=SESSION, D=self.commit, nonce=self.nonce, images=self.images, checkpoint=checkpoint,
 **self.window.binding, started=[time.clock_gettime_ns(c) for c in (time.CLOCK_MONOTONIC, time.CLOCK_BOOTTIME)])
  raw=canonical(request)
  self.guest.writer_request(raw)
  previous=request["started"].copy()
  def bounded():
   check(); self.check()
   now=[time.clock_gettime_ns(c) for c in (time.CLOCK_MONOTONIC, time.CLOCK_BOOTTIME)]
   require(all(s <= p <= n < s + 15000000000 for s, p, n in zip(request["started"], previous, now)),
 "GROWTH_WRITER_DEADLINE")
   previous[:]=now
  self.recheck()
  self.host.terminal_binding(self.terminal)
  argv=["/usr/bin/sudo", "--", "/usr/bin/env", "-i", "PATH=/usr/sbin:/usr/bin:/bin", "LANG=C", "LC_ALL=C",
 "/usr/bin/python3", "-I", "-B", "-c", self.guest.WRITER_LOADER,
 base64.b64encode(self.payload).decode(), digest(self.payload), base64.b64encode(raw).decode()]
  require(len(canonical(argv)) <= 65536, "GROWTH_WRITER_INPUT")
  self.io_bytes += len(canonical(argv))
  self.record(dict(writer_checkpoint=checkpoint, state="STARTED", request=request, argv_sha256=digest(canonical(argv))))
  command=self.host.Command(argv, bounded, limit=65536, stderr_limit=4096, terminal=True)
  child, counted=None, False
  try:
   result=command.collect()
   self.io_bytes += len(result["stdout"]) + len(result["stderr"])
   counted=True
   try:
    if result["returncode"] != 0:
     child=writer_failure(result["stdout"], request)
     failure=r.ObservationError(child["reason"])
     failure.errno=child["errno"]
     raise failure
   finally:
    self.host.terminal_binding(self.terminal)
   require(all(result["eof"].values()), "GROWTH_WRITER_FAILED")
   report=r.parse(result["stdout"], 65536)
   self.validate(report, request, checkpoint)
   self.reports.append(report)
   self.recheck(); bounded()
   self.record(dict(writer_checkpoint=checkpoint, state="RETURNED", report=report, exit=0,
 stderr=dict(bytes=len(result["stderr"]), sha256=digest(result["stderr"])), io_bytes=self.io_bytes))
   self.failed=False
   return report["rows"]
  except BaseException as error:
   if not counted: self.io_bytes += sum(map(len, command.output.values()))
   if child is None:
    try: child=writer_failure(bytes(command.output["stdout"]), request)
    except r.ObservationError: pass
   error.diagnostic=dict(checkpoint=checkpoint, pid=command.process.pid, exit=command.process.poll(), child_failure=child,
 streams={k: dict(bytes=len(v), sha256=digest(bytes(v))) for k, v in command.output.items()})
   raise
 def handoff(self):
  self.check()
  require(len(self.reports) == 1 and not self.failed, "GROWTH_WRITER_PREFLIGHT")
  usage=self.host.management_usage()
  return dict(report=self.reports[0], io_bytes=self.io_bytes, terminal=self.terminal,
 cpu_us=int(usage["cpu_seconds"] * 1000000) + self.reports[0]["usage"]["cpu_us"],
 rss_bytes=usage["rss_upper_observation_bytes"] + self.reports[0]["usage"]["peak_rss_bytes"])

def verify_writers(observations, expected_pid, expected_images):
 require(type(observations) is list and all(type(row) is dict for row in observations), "GROWTH_WRITERS")
 require(all(row.get("complete") is True for row in observations), "GROWTH_WRITERS_UNKNOWN")
 actual={(row["pid"], item) for row in observations for item in row["writable_images"]}
 expected=set() if expected_pid is None else {(expected_pid, item) for item in expected_images}
 require(actual == expected, "GROWTH_UNEXPECTED_WRITER")
