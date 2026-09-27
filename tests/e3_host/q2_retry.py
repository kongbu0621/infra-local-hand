"""Preserving, create-only preparation after the attested CPUQuota parser failure.

Only orchestration code lives here. Installed runtime candidates are never edited.
Every mutation is below a new reservation, except the explicitly approved single
start of a matching, normally inactive manager or parent slice.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import socket
import sqlite3
import stat
import struct
import time


def sibling(name):
    spec = importlib.util.spec_from_file_location('_retry_' + name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


p = sibling('q2_prepare')
c = p.c
SCHEMA = 'local-hand-q2-cpuquota-retry-preparation/v1'
ERROR = b"CPU quota '100.0000%' invalid.\n"
OWNER_FILES = {'reservation.json', 'delivery.json', 'capture.json', 'result.json',
               'stop.json', 'supervisor.stdout', 'supervisor.stderr', 'controls.json'}
REUSED = {'profile_work', 'profile_evidence', 'profile_temporary', 'store_parent'}
CATEGORIES = ('installation', 'state', 'journal', 'capture')


def legacy_argv(value, envelope_path, envelope_sha):
    """Reconstruct the historical bytes, not a repaired or reissued command."""
    fixture = value['fixture']; spec = fixture['supervisor_envelope']['controller']
    programs = fixture['launcher']['assembly']['installation']['programs']
    entry = fixture['launcher']['resident']['entry']['path']; suffix = '/tests/e3_host/q2_resident.py'
    c.require(entry.endswith(suffix), 'RETRY_OLD_SOURCE_LAYOUT'); source = entry[:-len(suffix)]
    rate = spec['cpu_quota_per_sec_usec']
    quota = str(rate // 10000) + '.' + f'{rate % 10000:04d}' + '%'
    properties = dict(User='root', Group='root', Slice=Path(spec['cgroup']).parent.name,
        Type='exec', ExitType='cgroup', RemainAfterExit='no', Restart='no', RestartForceExitStatus='',
        KillMode='control-group', SendSIGKILL='yes', FinalKillSignal='SIGKILL', NotifyAccess='none',
        ExecStartPre='', ExecStartPost='', ExecStop='', ExecStopPost='', ExecReload='', OnFailure='', OnSuccess='',
        RuntimeMaxSec=str(spec['runtime_max_usec'])+'us', RuntimeRandomizedExtraSec='0',
        TimeoutStopSec=str(spec['timeout_stop_usec'])+'us', TimeoutStopFailureMode='kill',
        MemoryMax=str(spec['memory_bytes']), MemorySwapMax='0', TasksMax=str(spec['tasks_max']), CPUQuota=quota,
        CPUQuotaPeriodSec='100ms', LimitCPU=str(spec['limit_cpu_seconds']), UMask='0077', WorkingDirectory='/',
        NoNewPrivileges='yes', CapabilityBoundingSet='CAP_DAC_READ_SEARCH CAP_SETGID CAP_SETUID CAP_SETPCAP CAP_SYS_ADMIN',
        AmbientCapabilities='', StandardInput='null')
    return [programs['systemd_run']['path'], '--system', '--quiet', '--wait', '--pipe', '--no-ask-password',
        '--unit='+spec['unit'], *('--property='+key+'='+val for key,val in properties.items()), '--',
        programs['python']['path'], '-I', '-B', source+'/tests/e3_host/q2_prepare_run.py',
        '--bind', '--envelope', envelope_path, '--sha256', envelope_sha]


def attest_startup(raw, envelope_raw, handoff_raw, old_prepared):
    """Pure exact failure attestation; absent service evidence alone is insufficient."""
    c.require(set(raw) == OWNER_FILES and raw['supervisor.stdout'] == b''
              and raw['supervisor.stderr'] == ERROR, 'RETRY_STARTUP_BOUNDARY')
    val = {name:c.document(data) for name,data in raw.items() if name.endswith('.json')}
    cap, result, delivery = val['capture.json'], val['result.json'], val['delivery.json']
    env = c.document(envelope_raw); handoff = c.document(handoff_raw)
    c.require(env['plan'] == handoff and env['schema'] == 'local-hand-q2-issued-handoff/v1', 'RETRY_OLD_ENVELOPE')
    c.require(cap.get('complete') is True and cap.get('returncode') == 1
        and cap.get('eof') == ['stderr','stdout'] and cap.get('error') is None and cap.get('close_errors') == []
        and cap.get('stdout_sha256') == p.sha(raw['supervisor.stdout'])
        and cap.get('stderr_sha256') == p.sha(raw['supervisor.stderr']), 'RETRY_OLD_CAPTURE')
    c.require(result.get('status') == 'INCOMPLETE' and result.get('reason') == 'SUPERVISOR_DELIVERY_UNCERTAIN'
        and result.get('sealed') is False and result.get('q2_accepted') is False
        and result.get('cleanup_errors') == [] and val['stop.json'] == {}, 'RETRY_OLD_VERDICT')
    envelope_path = handoff['declarations']['path']+'/envelope.json'
    argv = legacy_argv(env, envelope_path, p.sha(envelope_raw))
    c.require(delivery.get('argv_sha256') == p.sha(c.encoded(argv))
        and delivery.get('unit') == env['fixture']['supervisor_envelope']['controller']['unit']
        and delivery.get('started_ns') == cap.get('started_ns')
        and delivery.get('deadline_ns') == cap.get('deadline_ns') == handoff['owner_envelope']['deadline_ns'],
        'RETRY_OLD_COMMAND_BINDING')
    reservation = val['reservation.json']
    c.require(reservation.get('envelope_sha256') == p.sha(envelope_raw)
        and reservation.get('plan_sha256') == p.sha(handoff_raw), 'RETRY_OLD_ISSUANCE')
    controls = val['controls.json']; c.require(type(controls) is list and len(controls) == 2, 'RETRY_OLD_CONTROLS')
    for record in controls:
        c.require(record.get('complete') is True and record.get('returncode') == 0
            and record.get('eof') == ['stderr','stdout'] and record.get('error') is None
            and record.get('stderr_hex') == '', 'RETRY_OLD_CONTROLS')
        fields = dict(line.split('=',1) for line in bytes.fromhex(record['stdout_hex']).decode().splitlines())
        c.require(fields.get('Id') == delivery['unit'] and fields.get('LoadState') == 'not-found'
            and fields.get('ActiveState') == 'inactive' and fields.get('SubState') == 'dead'
            and fields.get('MainPID') == fields.get('ControlPID') == '0'
            and fields.get('InvocationID') == fields.get('ControlGroup') == fields.get('Job') == '', 'RETRY_OLD_CHILD_CREATED')
    c.require(old_prepared.get('status') == 'RECOVERED_PREPARED'
        and old_prepared.get('q2_accepted') is False
        and old_prepared['first_request_issuance']['original_request_unissued'] is True,
        'RETRY_OLD_PREPARATION')
    # The old preparation template was unissued then, but this later owner was
    # actually issued. Never propagate the historical template flag as current.
    return dict(original_owner_issued=True, argv_sha256=delivery['argv_sha256'],
        capture_sha256=p.sha(raw['capture.json']), failure='CPUQUOTA_PARSE_BEFORE_CHILD',
        original_status='INCOMPLETE', original_reason='SUPERVISOR_DELIVERY_UNCERTAIN')


LEDGER_SQL = """
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE operations(namespace TEXT NOT NULL,id TEXT NOT NULL,parent TEXT NOT NULL,
principal TEXT NOT NULL,digest TEXT NOT NULL,request_json TEXT NOT NULL,plan_json TEXT NOT NULL,
reserved_bytes INTEGER NOT NULL CHECK(reserved_bytes>0),record_json TEXT NOT NULL,PRIMARY KEY(namespace,id));
CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT,namespace TEXT NOT NULL,id TEXT NOT NULL,
kind TEXT NOT NULL,observed_at REAL NOT NULL,data_json TEXT NOT NULL);
CREATE TABLE leases(resource TEXT PRIMARY KEY,owner TEXT NOT NULL,epoch INTEGER NOT NULL);
CREATE TABLE revocations(principal TEXT PRIMARY KEY,generation INTEGER NOT NULL);
CREATE TABLE counters(key TEXT PRIMARY KEY,value INTEGER NOT NULL);
CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable events'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable events'); END;
CREATE TRIGGER identities_no_update BEFORE UPDATE OF namespace,id,parent,principal,digest,
request_json,plan_json,reserved_bytes ON operations BEGIN SELECT RAISE(ABORT,'immutable identity'); END;
CREATE TRIGGER operations_no_delete BEFORE DELETE ON operations BEGIN SELECT RAISE(ABORT,'immutable identity'); END;
"""


def canonical_sql(sql):
    tokens=re.findall(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[^\s]",sql or '')
    return ''.join(token if token.startswith(("'",'\"')) else token.lower() for token in tokens)


def ledger_schema(connection):
    return [(kind,name,table,canonical_sql(sql)) for kind,name,table,sql in
            connection.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name')]


def attest_ledger(path, pin, authority_id, guard=lambda:None):
    """Read an immutable, already existing DB; never run StateStore bootstrap."""
    guard(); c.require(str(path) == pin['path'], 'RETRY_LEDGER_PATH')
    for suffix in ('-wal','-shm','-journal'):
        c.require(not os.path.lexists(str(path)+suffix), 'RETRY_LEDGER_SIDECAR')
    fd = p.opened(str(path), owner=pin['uid'], noatime=True)
    try:
        before=os.fstat(fd)
        c.require((before.st_dev,before.st_ino,before.st_uid,stat.S_IMODE(before.st_mode)) ==
                  (pin['device'],pin['inode'],pin['uid'],pin['mode']) and stat.S_ISREG(before.st_mode)
                  and before.st_nlink == 1 and before.st_size <= 8*1024**2, 'RETRY_LEDGER_IDENTITY')
        raw=p.read_fd(fd,8*1024**2);digest=p.sha(raw)
        c.require(raw.startswith(b'SQLite format 3\0') and len(raw)>=100
            and raw[18:20] in (b'\1\1',b'\2\2'),'RETRY_LEDGER_FORMAT')
        # SQLite would reopen /proc/self/fd and lose O_NOATIME. Inspect only a
        # bounded RAM copy, normalizing a closed WAL database's header there.
        snapshot=bytearray(raw);snapshot[18:20]=b'\1\1'
        with closing(sqlite3.connect(':memory:')) as db:
            db.deserialize(bytes(snapshot))
            db.execute('PRAGMA query_only=ON'); db.execute('PRAGMA trusted_schema=OFF')
            db.set_progress_handler(lambda: (guard() or 0), 1000)
            c.require(db.execute('PRAGMA quick_check').fetchall()==[('ok',)],'RETRY_LEDGER_INTEGRITY')
            with closing(sqlite3.connect(':memory:')) as expected:
                expected.executescript(LEDGER_SQL)
                c.require(ledger_schema(db)==ledger_schema(expected),'RETRY_LEDGER_SCHEMA')
            metadata=dict(db.execute('SELECT key,value FROM metadata'))
            c.require(metadata==dict(schema='1',authority_id=authority_id,ledger_id=pin['ledger_id']), 'RETRY_LEDGER_METADATA')
            c.require(pin['generation']==[1,1] and list(db.execute('SELECT key,value FROM counters'))==[('generation',1)],
                      'RETRY_LEDGER_GENERATION')
            for table in ('operations','events','leases','revocations','sqlite_sequence'):
                c.require(db.execute('SELECT COUNT(*) FROM '+table).fetchone()==(0,), 'RETRY_LEDGER_CONSUMED')
        after=os.fstat(fd)
        c.require(all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_atime_ns','st_mtime_ns','st_ctime_ns'))
            and digest==p.sha(p.read(path,8*1024**2,owner=pin['uid'],noatime=True)), 'RETRY_LEDGER_CHANGED')
        for suffix in ('-wal','-shm','-journal'):
            c.require(not os.path.lexists(str(path)+suffix),'RETRY_LEDGER_SIDECAR')
        guard(); return dict(pin,authority_id=authority_id,sha256=digest,unused=True)
    finally: os.close(fd)


def require_members(path, expected, code, *, owner=0):
    """Check old directory membership without altering its access time."""
    fd=p.opened(path,directory=True,owner=owner,noatime=True)
    try:
        names=set()
        with os.scandir(fd) as entries:
            for entry in entries:
                c.require(entry.name in expected and entry.name not in names,code)
                names.add(entry.name)
        c.require(names==set(expected),code)
    finally:os.close(fd)


def snapshot_tree(path, guard, *, maximum_bytes=256*1024**2, maximum_entries=32768, seen=None, hash_files=True):
    """Bounded no-follow tree snapshot; all physical blocks are charged once."""
    pending=[Path(path)]; rows=[]; total=0; logical=0; seen=set() if seen is None else seen; device=None
    while pending:
        guard(); name=pending.pop(); info=name.lstat(); key=(info.st_dev,info.st_ino)
        c.require(key not in seen and not stat.S_ISLNK(info.st_mode), 'RETRY_TREE_ALIAS')
        if device is None: device=info.st_dev
        c.require(info.st_dev==device, 'RETRY_TREE_MOUNT'); seen.add(key)
        row=p.identity(info,str(name)); row.update(size=info.st_size,mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns)
        total+=max(info.st_size,info.st_blocks*512); logical+=info.st_size
        c.require(len(rows)+1 <= maximum_entries and total <= maximum_bytes, 'RETRY_TREE_LIMIT')
        if stat.S_ISDIR(info.st_mode):
            fd=p.opened(str(name),directory=True,owner=info.st_uid,noatime=True)
            try:
                c.require(p.identity(os.fstat(fd))==p.identity(info),'RETRY_TREE_CHANGED')
                for entry in os.scandir(fd):
                    c.require(len(pending)+len(rows)<maximum_entries,'RETRY_TREE_LIMIT')
                    pending.append(name/entry.name)
            finally:os.close(fd)
        else:
            c.require(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'RETRY_TREE_TYPE')
            if hash_files:row['sha256']=p.sha(p.read(name,maximum_bytes,owner=info.st_uid,noatime=True))
        rows.append(row)
    return dict(path=str(path),bytes=total,inodes=len(rows),logical_bytes=logical,
                sha256=p.sha(c.encoded(sorted(rows,key=lambda row:row['path']))))


class RetryBackend(p.LinuxBackend):
    def __init__(self, plan, retry, issued_ns, deadline_ns, *, boot_deadline_ns=None, original_plan=None):
        super().__init__(plan)
        c.require(type(issued_ns) is int and type(deadline_ns) is int and
            issued_ns <= time.monotonic_ns() < deadline_ns <= issued_ns+140*10**9, 'RETRY_DEADLINE')
        self.issued_ns=issued_ns; self.deadline=deadline_ns; self.boot_deadline_ns=boot_deadline_ns
        self.retry=retry; self.old = original_plan
        if self.old is None:
            self.old=c.decode(p.read(retry['original_plan_path'],c.LIMIT,noatime=True),retry['original_plan_sha256'])
        self.old_snapshots=None; self.old_hashes={}; self.old_prepared=None; self.old_handoff=None
        self.attestation=None; self.costs={}; self.candidate_checked=False; self.started=set(); self.configuration={}
        self.skip_candidate=False; self.old_storage_commitment=None

    def guard(self):
        c.require(time.monotonic_ns()<self.deadline and (self.boot_deadline_ns is None or
            time.clock_gettime_ns(time.CLOCK_BOOTTIME)<self.boot_deadline_ns), 'RETRY_DEADLINE')

    def command(self, argv, *, env=None):
        self.guard()
        c.require(type(argv) in (list, tuple) and 1 <= len(argv) <= 128
                  and all(type(a) is str and len(a) <= 65536 and "\0" not in a for a in argv), "PREPARE_COMMAND")
        argv_record=c.encoded({"argv":list(argv)})
        c.require(len(argv_record)<=32768,"PREPARE_COMMAND_ARGV_LIMIT")
        if self.reservation is not None:
            # Admit intent, maximum result, block overhead and final report
            # before process creation; exhausted capture budgets never launch.
            reserve=len(argv_record)*2+2*self.plan["budgets"]["command_output_bytes"]+3*self.log_block
            c.require(self.sequence+2<=self.max_events and self.sequence+6<=self.log_inode_limit
                      and self.log_bytes+reserve+c.LIMIT<=self.log_byte_limit,"PREPARE_COMMAND_RECORD_BUDGET")
        self.event("command-intent", {"argv": list(argv)})
        deadline = min(self.deadline - 10**9, time.monotonic_ns() + self.plan["budgets"]["command_seconds"] * 10**9)
        c.require(time.monotonic_ns()<deadline and (self.boot_deadline_ns is None or
            time.clock_gettime_ns(time.CLOCK_BOOTTIME)<self.boot_deadline_ns-10**9),'RETRY_COMMAND_STOP_RESERVE')
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=p.ENV if env is None else env, close_fds=True, start_new_session=True)
        selector = selectors.DefaultSelector(); output = {"stdout": bytearray(), "stderr": bytearray()}
        eof = set(); failure = None
        for name in output:
            stream = getattr(proc, name); os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, name)
        try:
            while len(eof) != 2 or proc.poll() is None:
                if time.monotonic_ns() >= deadline or (self.boot_deadline_ns is not None and
                    time.clock_gettime_ns(time.CLOCK_BOOTTIME) >= self.boot_deadline_ns - 10**9):
                    failure = "PREPARE_COMMAND_TIMEOUT"; break
                for key, _ in selector.select(min(0.05, max(0, (deadline-time.monotonic_ns())/10**9))):
                    block = os.read(key.fd, 4096)
                    if not block:
                        eof.add(key.data); selector.unregister(key.fileobj); continue
                    room = self.plan["budgets"]["command_output_bytes"] - sum(map(len, output.values()))
                    output[key.data].extend(block[:room])
                    if len(block) > room: failure = "PREPARE_COMMAND_OUTPUT_LIMIT"; break
                if failure: break
            if failure:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                try: proc.wait(timeout=1)
                except subprocess.TimeoutExpired: pass
            result = {"argv": list(argv), "returncode": proc.poll(), "eof": sorted(eof), "failure": failure,
                      **{name: bytes(raw).hex() for name, raw in output.items()}}
            unsuccessful=failure is not None or len(eof)!=2 or proc.returncode!=0
            if unsuccessful:
                # The durable command result keeps the original bounded bytes.
                # Include a small readable diagnosis in the batch receipt too,
                # so a failed command does not require another host round trip.
                self.last_command_failure={"argv":list(argv),"returncode":proc.poll(),"eof":sorted(eof),
                    "failure":failure,"record":None if self.reservation is None else
                        str(self.reservation/f"{self.sequence+1:04d}-command-result.json"),
                    "record_sha256":p.sha(c.encoded(result)),"record_saved":False,
                    "stdout":bytes(output["stdout"][:4096]).decode("utf-8",errors="replace"),
                    "stderr":bytes(output["stderr"][:4096]).decode("utf-8",errors="replace"),
                    "summary_truncated":{name:len(value)>4096 for name,value in output.items()}}
            if self.reservation is None:
                self.preflight_commands.append(len(argv_record)+len(c.encoded(result)))
            self.event("command-result", result)
            if unsuccessful:
                self.last_command_failure["record_saved"]=self.reservation is not None
            c.require(failure is None and len(eof) == 2 and proc.returncode == 0,
                      failure or "PREPARE_COMMAND_FAILED")
            return bytes(output["stdout"])
        finally:
            if proc.poll() is None:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                try: proc.wait(timeout=1)
                except subprocess.TimeoutExpired: pass
            selector.close()
            for name in output: getattr(proc, name).close()

    def old_file_owner(self,name):
        for role,item in self.old['directories'].items():
            if item['owner']=='ordinary' and (Path(name)==Path(item['path']) or Path(item['path']) in Path(name).parents):
                return self.plan['account']['uid']
        return 0

    def old_document(self,name):
        c.require(name in self.retry['old_files'], 'RETRY_OLD_PIN_MISSING')
        raw=p.read(name,c.LIMIT,owner=self.old_file_owner(name),noatime=True)
        c.require(p.sha(raw)==self.retry['old_files'][name], 'RETRY_OLD_FILE_CHANGED')
        return c.document(raw)

    def verify_old_hashes(self):
        for name,digest in self.retry['old_files'].items():
            self.guard(); c.require(p.sha(p.read(name,c.LIMIT,owner=self.old_file_owner(name),noatime=True))==digest,'RETRY_OLD_FILE_CHANGED')

    def account(self):
        import pwd,grp
        self.guard(); a=self.plan['account']; old=self.old
        entry=pwd.getpwnam(a['name']); group=grp.getgrnam(a['name'])
        c.require(entry==pwd.getpwuid(a['uid']) and group==grp.getgrgid(a['gid'])
            and (entry.pw_uid,entry.pw_gid,entry.pw_dir,entry.pw_shell)==
            (a['uid'],a['gid'],old['directories']['state']['path'],'/usr/sbin/nologin')
            and group.gr_mem==[] and os.getgrouplist(a['name'],a['gid'])==[a['gid']], 'RETRY_ACCOUNT_CHANGED')
        return dict(a)

    def old_root_pins(self):
        result={}
        phases=self.old_handoff['template']['launcher']['assembly']['phases']
        for phase in phases.values():
            grant=phase['grant']; pins=grant['allocation']['paths']
            for root in grant['roots']:
                matching=[path for path,pin in pins.items() if (pin['device'],pin['inode'])==(root['device'],root['inode'])]
                c.require(len(matching)==1,'RETRY_OLD_ROOT_PIN')
                row=dict(root,path=matching[0]); prior=result.get(row['project_id'])
                c.require(prior is None or prior==row,'RETRY_OLD_ROOT_PIN');result[row['project_id']]=row
        c.require(len(result)==7,'RETRY_OLD_ROOT_COUNT');return result

    def roots(self):
        self.guard(); plan=self.plan; pins=self.old_root_pins(); quota=p.Quota(plan['mounts']['quota']['source'])
        enforcement=quota.enforcement(); result=[]
        for root in plan['roots']:
            self.guard(); pin=pins[root['project_id']]
            fd=p.opened(root['path'],directory=True,owner=plan['account']['uid'],noatime=True)
            try:
                info=p.identity(os.fstat(fd),root['path'])
                c.require(all(info[key]==pin[key] for key in ('path','device','inode','uid','gid','mode')),'RETRY_ROOT_IDENTITY')
                c.require(not any(os.scandir(fd)),'RETRY_ROOT_CONSUMED')
                flags,_,_,project,_,_=struct.unpack('=IIIII8s',fcntl.ioctl(fd,0x801c581f,bytes(28)))
                block=quota.block(root['project_id'])
                c.require(project==root['project_id'] and flags==pin['xflags'] and flags&512
                    and block['valid']&5==5 and block['hard']*1024==root['hard_bytes']==pin['hard_bytes']
                    and block['ihard']==root['inode_hard_limit'] and block['inodes']==1
                    and block['space']==os.fstat(fd).st_blocks*512
                    and all(block[key]==0 for key in ('soft','isoft','btime','itime')),'RETRY_ROOT_QUOTA_CHANGED')
                c.require(p.identity(os.fstat(fd),root['path'])==info,'RETRY_ROOT_IDENTITY')
                result.append(dict(root,**{key:value for key,value in info.items() if key!='path'},
                    filesystem='ext4',filesystem_uuid=plan['mounts']['quota']['uuid'],xflags=flags,
                    accounting=bool(enforcement&16),enforcement=bool(enforcement&32),identity_unchanged=True))
            finally:os.close(fd)
        # Parent membership must be the original slot roots only; store_parent
        # containing its prepared store root is expected, not payload consumption.
        for role in REUSED:
            path=Path(plan['directories'][role]['path'])
            expected={Path(root['path']).name for root in plan['roots'] if Path(root['path']).parent==path}
            fd=p.opened(str(path),directory=True,owner=plan['account']['uid'],noatime=True)
            try:c.require({entry.name for entry in os.scandir(fd)}==expected,'RETRY_PROFILE_CONSUMED')
            finally:os.close(fd)
        return result

    def unit_show(self,unit,ordinary=False):
        argv=[self.tool('systemctl'),'--user' if ordinary else '--system','show',unit,
          '--property=Id,LoadState,ActiveState,SubState,ControlGroup,User,Delegate,MainPID,ControlPID,Job,InvocationID,FragmentPath,DropInPaths,MemoryMax,MemorySwapMax,TasksMax,CPUQuotaPerSecUSec']
        raw=self.user_command(argv) if ordinary else self.command(argv)
        return dict(line.split('=',1) for line in raw.decode().splitlines() if '=' in line)

    def idle_unit(self,unit,ordinary=False,manager=False):
        value=self.unit_show(unit,ordinary)
        c.require(value.get('Id')==unit and value.get('LoadState')=='loaded'
            and value.get('ActiveState') in ('active','inactive') and value.get('Job') in ('','0'), 'RETRY_UNIT_STATE')
        if value['ActiveState']=='inactive':
            c.require(value.get('SubState')=='dead' and (value.get('MainPID')==value.get('ControlPID')=='0'
                if manager else value.get('ControlGroup','')==''),'RETRY_UNIT_STATE')
        elif manager:
            c.require(value.get('SubState')=='running' and value.get('ControlPID')=='0'
                and value.get('User')==str(self.plan['account']['uid']) and value.get('Delegate')=='yes','RETRY_MANAGER_DELEGATION')
        else:
            group=value.get('ControlGroup',''); c.path(group)
            path=Path('/sys/fs/cgroup')/group.lstrip('/')
            events=dict(line.split() for line in p.kernel(str(path/'cgroup.events')).decode().splitlines())
            c.require(events.get('populated')=='0' and p.kernel(str(path/'cgroup.procs')).strip()==b'', 'RETRY_PARENT_BUSY')
        return value

    def configuration_files(self):
        a=self.plan['account'];ordinary=self.plan['parents']['ordinary'];instance=f"user@{a['uid']}.service"
        manager=("[Service]\nDelegate=cpu memory pids\nCPUAccounting=yes\nCPUQuota="
            +c.cpu_quota_percent(ordinary['cpu_quota_per_sec_usec'])+"\nCPUQuotaPeriodSec=100ms\nMemoryAccounting=yes\nMemoryMax="
            +str(ordinary['memory_bytes'])+"\nMemorySwapMax=0\nTasksAccounting=yes\nTasksMax="+str(ordinary['tasks_max'])+"\n").encode()
        files={f'/etc/systemd/system/{instance}.d/50-local-hand-q2.conf':manager}
        files.update({'/etc/systemd/system/'+self.plan['parents'][role]['unit']:self.slice_bytes(self.plan['parents'][role])
                      for role in c.SYSTEM_PARENTS})
        files[f"/run/user/{a['uid']}/systemd/user/"+ordinary['unit']]=self.slice_bytes(ordinary)
        for name,expected in files.items():
            owner=a['uid'] if name.startswith('/run/user/') else 0
            c.require(p.read(name,65536,owner=owner,noatime=True)==expected,'RETRY_CONFIGURATION_CHANGED')
        for role,row in self.plan['parents'].items():
            bases=(f"/run/user/{a['uid']}/systemd/user/", f"{self.old['directories']['state']['path']}/.config/systemd/user/", '/etc/systemd/user/', '/usr/lib/systemd/user/') if role=='ordinary' else ('/etc/systemd/system/','/run/systemd/system/','/usr/lib/systemd/system/')
            canonical=next(name for name in files if name.endswith('/'+row['unit']))
            for base in bases:
                c.require(not os.path.lexists(base+row['unit']+'.d'),'RETRY_CONFIGURATION_DROPIN')
                if base+row['unit']!=canonical:
                    c.require(not os.path.lexists(base+row['unit']),'RETRY_CONFIGURATION_SHADOW')
        drop=Path(f'/etc/systemd/system/{instance}.d')
        require_members(drop,{'50-local-hand-q2.conf'},'RETRY_MANAGER_DROPIN')
        for base in ('/run/systemd/system/','/usr/lib/systemd/system/'):
            c.require(not os.path.lexists(base+instance+'.d') and not os.path.lexists(base+instance),'RETRY_MANAGER_SHADOW')
        return {name:p.sha(raw) for name,raw in files.items()}

    def manager_limits(self,manager):
        expected=self.plan['parents']['ordinary'];group=manager.get('ControlGroup','');c.path(group)
        path=Path('/sys/fs/cgroup')/group.lstrip('/')
        for name,value in (('memory.max',expected['memory_bytes']),('memory.swap.max',0),('pids.max',expected['tasks_max'])):
            c.require(p.kernel(str(path/name)).strip()==str(value).encode(),'RETRY_MANAGER_LIMIT')
        quota,period=map(int,p.kernel(str(path/'cpu.max')).split())
        c.require(quota*1000000==period*expected['cpu_quota_per_sec_usec'],'RETRY_MANAGER_CPU')

    def start_once(self,unit,ordinary=False):
        manager=f"user@{self.plan['account']['uid']}.service"
        allowed={row['unit'] for row in self.plan['parents'].values()}|{manager}
        c.require(unit in allowed and ordinary==(unit==self.plan['parents']['ordinary']['unit']),'RETRY_START_SCOPE')
        c.require(unit not in self.started,'RETRY_START_ALREADY_ISSUED');self.started.add(unit)
        self.event('start-intent',dict(unit=unit,ordinary=ordinary))
        argv=[self.tool('systemctl'),'--user' if ordinary else '--system','start',unit]
        if ordinary:self.user_command(argv)
        else:self.command(argv)
        self.event('start-result',dict(unit=unit,ordinary=ordinary))

    def parent_limits(self,row,group):
        c.path(group);location=Path('/sys/fs/cgroup')/group.lstrip('/')
        c.require({'cpu','memory','pids'}<=set(p.kernel(str(location/'cgroup.controllers')).decode().split()),'RETRY_CONTROLLERS')
        for name,expected in (('memory.max',row['memory_bytes']),('memory.swap.max',0),('pids.max',row['tasks_max'])):
            c.require(p.kernel(str(location/name)).strip()==str(expected).encode(),'RETRY_PARENT_LIMIT')
        quota,period=map(int,p.kernel(str(location/'cpu.max')).split())
        c.require(quota*1000000==period*row['cpu_quota_per_sec_usec'],'RETRY_PARENT_CPU')

    def check_parents(self,*,start=False):
        configuration=self.configuration_files()
        if self.configuration:c.require(configuration==self.configuration,'RETRY_CONFIGURATION_CHANGED')
        self.configuration=configuration;a=self.plan['account'];instance=f"user@{a['uid']}.service"
        manager=self.idle_unit(instance,manager=True)
        # The manager's own init.scope is expected. Any other populated child
        # apart from the approved empty dedicated ordinary slice is not idle.
        if manager['ActiveState']=='active':
            self.manager_limits(manager)
            group=Path('/sys/fs/cgroup')/manager['ControlGroup'].lstrip('/')
            for entry in os.scandir(group):
                if not entry.is_dir(follow_symlinks=False) or entry.name=='init.scope':continue
                events=dict(line.split() for line in p.kernel(str(Path(entry.path)/'cgroup.events')).decode().splitlines())
                c.require(events.get('populated')=='0','RETRY_MANAGER_OTHER_WORK')
        states={role:self.idle_unit(row['unit']) for role,row in self.plan['parents'].items() if role!='ordinary'}
        if manager['ActiveState']=='active':states['ordinary']=self.idle_unit(self.plan['parents']['ordinary']['unit'],True)
        for role,state in states.items():
            if state['ActiveState']=='active':self.parent_limits(self.plan['parents'][role],state['ControlGroup'])
        if not start:return dict(manager=manager,parents=states,configuration=configuration)
        if manager['ActiveState']=='inactive':self.start_once(instance)
        manager=self.idle_unit(instance,manager=True)
        c.require(manager['ActiveState']=='active' and manager['SubState']=='running' and manager['User']==str(a['uid'])
            and manager['Delegate']=='yes','RETRY_MANAGER_DELEGATION')
        self.manager_limits(manager)
        states['ordinary']=self.idle_unit(self.plan['parents']['ordinary']['unit'],True)
        result={}
        for role,row in self.plan['parents'].items():
            if states[role]['ActiveState']=='inactive':self.start_once(row['unit'],role=='ordinary')
            current=self.idle_unit(row['unit'],role=='ordinary')
            c.require(current['ActiveState']=='active','RETRY_PARENT_INACTIVE');group=current['ControlGroup']
            c.require(group=='/'+row['unit'] if role!='ordinary' else str(Path(group).parent)==manager['ControlGroup'], 'RETRY_PARENT_PATH')
            location=Path('/sys/fs/cgroup')/group.lstrip('/');info=p.identity(location.stat(),group)
            c.require({'cpu','memory','pids'}<=set(p.kernel(str(location/'cgroup.controllers')).decode().split()),'RETRY_CONTROLLERS')
            for name,expected in (('memory.max',row['memory_bytes']),('memory.swap.max',0),('pids.max',row['tasks_max'])):
                c.require(p.kernel(str(location/name)).strip()==str(expected).encode(),'RETRY_PARENT_LIMIT')
            quota,period=map(int,p.kernel(str(location/'cpu.max')).split())
            c.require(quota*1000000==period*row['cpu_quota_per_sec_usec'],'RETRY_PARENT_CPU')
            if role=='ordinary':
                st=(location/'cgroup.procs').stat();c.require(st.st_uid==a['uid'] and st.st_mode&0o200,'RETRY_DELEGATION')
            result[role]=dict(info,**row)
        for name in ('cgroup.controllers','cgroup.subtree_control'):
            c.require({'cpu','memory','pids'}<=set(p.kernel('/sys/fs/cgroup'+manager['ControlGroup']+'/'+name).decode().split()),'RETRY_MANAGER_CONTROLLERS')
        result['manager']=dict(unit=instance,**manager);return result

    def mounts(self):
        rows=p.kernel('/proc/self/mountinfo',1024*1024).decode().splitlines();result={}
        for role,expected in self.plan['mounts'].items():
            self.guard();selected=[line.split() for line in rows if line.split()[4]==expected['path']]
            c.require(len(selected)==1,'RETRY_MOUNT_AMBIGUOUS');row=selected[0];sep=row.index('-')
            major,minor=map(int,row[2].split(':'));device=os.makedev(major,minor)
            c.require(row[3]=='/' and device==expected['device']==os.stat(expected['path']).st_dev
                and row[sep+1]==expected['filesystem'] and row[sep+2]==expected['source']
                and 'rw' in row[5].split(','),'RETRY_MOUNT_CHANGED')
            info=os.stat(expected['source']);c.require(stat.S_ISBLK(info.st_mode) and info.st_rdev==device,'RETRY_BLOCK_DEVICE')
            uuid=self.command([self.tool('blkid'),'-p','-s','UUID','-o','value',expected['source']]).decode().strip()
            c.require(uuid==expected['uuid'],'RETRY_FILESYSTEM_UUID')
            if role=='quota':c.require('prjquota' in set(row[5].split(',')+row[sep+3].split(',')),'RETRY_PROJECT_MOUNT')
            fs=os.statvfs(expected['path']);result[role]=dict(expected,available_bytes=fs.f_bavail*fs.f_frsize,
                free_inodes=fs.f_favail,total_bytes=fs.f_blocks*fs.f_frsize,total_inodes=fs.f_files,block_bytes=fs.f_frsize)
        return result

    def new_staging(self,item):
        root=Path(item['path'])
        candidates=[self.plan['candidate'][key] for key in ('source','wheel')]
        candidates+=list(self.retry['source']['files'])
        intent=str(Path(self.plan['candidate']['source']).parent)+'.intent.json'
        return item['category']=='installation' and (str(root)==intent or any(root==Path(name) or root in Path(name).parents for name in candidates))

    def old_snapshot(self):
        return [snapshot_tree(item['path'],self.guard) for item in self.retry['retained_inputs'] if not self.new_staging(item)]

    def measure_costs(self):
        items=list(self.retry['retained_inputs']);mapping={'reservation':'state','state':'state','authority':'state',
            'journal':'journal','capture':'capture','declarations':'capture','session':'state','control':'state'}
        for role,category in mapping.items():
            name=self.plan['directories'][role]['path']
            if os.path.lexists(name):items.append(dict(path=name,category=category))
        for key in ('source','wheel','destination'):
            name=self.plan['candidate'][key]
            if os.path.lexists(name) and not any(name==item['path'] or Path(item['path']) in Path(name).parents for item in items):
                items.append(dict(path=name,category='installation'))
        costs={role:dict(bytes=0,inodes=0) for role in CATEGORIES};seen=set();old_capture=dict(bytes=0,inodes=0);new_capture=dict(bytes=0,inodes=0)
        for item in items:
            if not os.path.lexists(item['path']) and self.skip_candidate and self.new_staging(item):continue
            value=snapshot_tree(item['path'],self.guard,seen=seen,hash_files=False)
            for key in ('bytes','inodes'):costs[item['category']][key]+=value[key]
            if item['category']=='capture':
                charge=old_capture if item in self.retry['retained_inputs'] else new_capture
                for key in ('bytes','inodes'):charge[key]+=value[key]
        for category,value in costs.items():
            for key in ('bytes','inodes'):
                c.require(value[key]<=self.plan['budgets'][category+'_'+key],'RETRY_CUMULATIVE_CAPACITY')
        if self.old_storage_commitment is not None:
            # Historical retained owner reservation is not refunded. New runtime
            # commitment is additional, while current occupancy is reported apart.
            settings=self.plan['settings'];new_bytes=3*settings['management']['storage_bytes']+settings['owner']['storage_bytes']
            new_inodes=3*settings['management']['storage_inodes']+settings['owner']['storage_inodes']
            for control in settings['controllers'].values():
                new_bytes+=control['storage_bytes'];new_inodes+=control['storage_inodes']
            old=self.old_storage_commitment
            for key,new_value in (('bytes',new_bytes),('inodes',new_inodes)):
                retained=old['storage_'+key]
                costs['capture']['retained_commitment_'+key]=retained
                costs['capture']['new_runtime_commitment_'+key]=new_value
                old_unspent=max(0,retained-old_capture[key]);new_unspent=max(0,new_value-new_capture[key])
                costs['capture']['retained_unspent_'+key]=old_unspent
                costs['capture']['new_runtime_unspent_'+key]=new_unspent
                costs['capture']['admitted_'+key]=costs['capture'][key]+old_unspent+new_unspent
                c.require(costs['capture']['admitted_'+key]<=self.plan['budgets']['capture_'+key],
                          'RETRY_RETAINED_COMMITMENT_CAPACITY')
        self.costs=costs;return costs

    def capacity(self,mounts,inventory):
        costs=self.measure_costs(); seen=set();quota_bytes=quota_inodes=used_bytes=used_inodes=0
        for row in inventory:
            key=(self.plan['mounts']['quota']['uuid'],row['project'])
            c.require(key not in seen,'RETRY_DOMAIN_ALIAS');seen.add(key)
            quota_bytes+=row['hard']*1024;quota_inodes+=row['ihard'];used_bytes+=row['space'];used_inodes+=row['inodes']
        commitments={role:dict(bytes=0,inodes=0) for role in mounts}
        commitments['quota']=dict(bytes=quota_bytes,inodes=quota_inodes)
        # Full retained ceilings are conservative commitments, not refunds of
        # consumed space. Available bytes already exclude current occupancy.
        mapping={'installation':{'system'},'state':{self.plan['directories'][r]['filesystem'] for r in ('reservation','state','authority','session','control')},
          'journal':{self.plan['directories']['journal']['filesystem']},
          'capture':{self.plan['directories'][r]['filesystem'] for r in ('capture','declarations')}}
        for category,roles in mapping.items():
            for role in roles:
                commitments[role]['bytes']+=self.plan['budgets'][category+'_bytes']
                commitments[role]['inodes']+=self.plan['budgets'][category+'_inodes']
        by_device={}
        for role,row in mounts.items():
            prior=by_device.setdefault(row['device'],dict(bytes=0,inodes=0,available_bytes=row['available_bytes'],free_inodes=row['free_inodes']))
            for key in ('bytes','inodes'):prior[key]+=commitments[role][key]
        for row in by_device.values():c.require(row['bytes']<=row['available_bytes'] and row['inodes']<=row['free_inodes'],'RETRY_CAPACITY_INSUFFICIENT')
        return dict(commitments=commitments,quota_inventory=inventory,cumulative_actual=costs,
            quota_unique=dict(hard_bytes=quota_bytes,hard_inodes=quota_inodes,used_bytes=used_bytes,used_inodes=used_inodes,
                unspent_bytes=sum(max(0,row['hard']*1024-row['space']) for row in inventory)),by_device=by_device)

    def verify_candidate(self):
        self.guard();build=p.sibling('q2_prepare_build');candidate=self.plan['candidate'];source=Path(candidate['source'])
        build.parents(source,protected=True);build.bounded_inventory(source,protected=True)
        files=build.verify_source(source,candidate['commit'],candidate['tree'],self.command)
        build.verify_wheel(Path(candidate['wheel']),candidate['wheel_sha256'],candidate['commit'],files)
        for name,digest in self.retry['source']['files'].items():
            self.guard();c.require(p.sha(p.read(name,c.LIMIT,noatime=True))==digest,'RETRY_ORCHESTRATION_SOURCE_CHANGED')
        required={str(Path(__file__).with_name(name+'.py')) for name in ('q2_retry','q2_retry_contract','q2_retry_driver','q2_prepare','q2_prepare_contract','q2_prepare_build')}
        c.require(required<=set(self.retry['source']['files']),'RETRY_ORCHESTRATION_CLOSURE')
        self.candidate_checked=True

    def preflight(self,*,skip_candidate=False):
        self.guard();plan=self.plan;self.skip_candidate=skip_candidate
        c.require(os.getuid()==os.geteuid()==os.getgid()==os.getegid()==0 and p.kernel('/proc/1/comm').strip()==b'systemd','RETRY_ROOT_SYSTEMD')
        ns=os.stat('/proc/self/ns/user');init=os.stat('/proc/1/ns/user')
        actual=dict(hostname=socket.gethostname(),boot_id=p.kernel('/proc/sys/kernel/random/boot_id').decode().strip(),
            initial_userns=dict(device=ns.st_dev,inode=ns.st_ino),dmi_vendor=p.kernel('/sys/class/dmi/id/sys_vendor').decode().strip(),
            dmi_product=p.kernel('/sys/class/dmi/id/product_name').decode().strip())
        c.require(actual==plan['host']==self.old['host'] and (ns.st_dev,ns.st_ino)==(init.st_dev,init.st_ino),'RETRY_GUEST_CHANGED')
        self.verify_old_hashes();self.old_prepared=self.old_document(self.retry['old_prepared']);self.old_handoff=self.old_document(self.retry['old_handoff'])
        c.require(self.old_prepared['ledger']==self.retry['old_ledger'],'RETRY_LEDGER_BINDING')
        self.account()
        for tool in plan['tools'].values():
            self.guard();raw=p.read(tool['path'],64*1024**2,noatime=True)
            c.require(raw.startswith(b'\x7fELF') and p.sha(raw)==tool['sha256'] and os.stat(tool['path']).st_mode&0o111,'RETRY_TOOL_CHANGED')
        self.verify_old_service_exit();self.verify_old_source()
        owner=Path(self.retry['old_owner_output']);require_members(owner,OWNER_FILES,'RETRY_OWNER_MEMBERS')
        raw={name:p.read(owner/name,c.LIMIT,noatime=True) for name in OWNER_FILES}
        envelope_path=self.old_handoff['declarations']['path']+'/envelope.json'
        c.require(envelope_path in self.retry['old_files'],'RETRY_OLD_PIN_MISSING');env_raw=p.read(envelope_path,c.LIMIT,noatime=True)
        startup=attest_startup(raw,env_raw,p.read(self.retry['old_handoff'],c.LIMIT,noatime=True),self.old_prepared)
        self.old_storage_commitment=c.document(raw['reservation.json'])['costs']
        # Only the issued envelope exists; any child binding or output means the
        # parser-only boundary cannot justify reusing these roots.
        require_members(self.old_handoff['declarations']['path'],{'envelope.json'},'RETRY_OLD_CHILD_CREATED')
        fixture=c.document(env_raw)['fixture']
        for pin in (fixture['declarations'],fixture['output'],fixture['launcher']['declarations'],fixture['launcher']['output']):
            require_members(pin['path'],set(),'RETRY_OLD_CHILD_CREATED')
        for name in (fixture['supervisor_envelope']['controller']['unit'],fixture['launcher']['controller_envelope']['controller']['unit']):
            value=self.unit_show(name)
            c.require(value.get('LoadState')=='not-found' and value.get('ActiveState')=='inactive'
                and value.get('MainPID')==value.get('ControlPID')=='0' and value.get('Job') in ('','0')
                and value.get('InvocationID')=='','RETRY_OLD_CHILD_CREATED')
        policy=self.old_document(self.old_prepared['policy']['path'])
        ledger=attest_ledger(self.retry['old_ledger']['path'],self.retry['old_ledger'],policy['authority_id'],self.guard)
        roots=self.roots();mounts=self.mounts();quota=p.Quota(plan['mounts']['quota']['source']);inventory=quota.inventory(self.guard)
        for retained in plan['retained_domains']:
            matches=[r for r in inventory if r['project']==retained['project_id']]
            c.require(len(matches)==1 and matches[0]['hard']*1024==retained['hard_bytes']
                and matches[0]['ihard']==retained['inode_hard_limit'],'RETRY_RETAINED_QUOTA_CHANGED')
        for role,item in plan['directories'].items():
            if role not in REUSED:self.absent(item['path'],device=plan['mounts'][item['filesystem']]['device'])
        self.absent(plan['candidate']['destination'],device=plan['mounts']['system']['device'])
        targets=[plan['candidate']['destination'],*[item['path'] for role,item in plan['directories'].items()
            if role not in REUSED and (item['owner']=='ordinary' or role in ('control','session','declarations'))]]
        a=plan['account']
        for target in targets:
            for ancestor in reversed(Path(target).parents):
                info=ancestor.stat();shift=6 if info.st_uid==a['uid'] else 3 if info.st_gid==a['gid'] else 0
                c.require(info.st_mode>>shift&5==5,'RETRY_ORDINARY_ANCESTOR_ACCESS')
                for key in ('system.posix_acl_access','system.posix_acl_default'):
                    try:os.getxattr(ancestor,key,follow_symlinks=False)
                    except OSError as error:
                        if error.errno in (errno.ENODATA,errno.ENOTSUP,errno.EOPNOTSUPP):continue
                        raise
                    raise ValueError('RETRY_ANCESTOR_ACL_UNPROVEN')
        self.check_parents()
        if not skip_candidate:self.verify_candidate()
        old=self.old_snapshot()
        if self.old_snapshots is not None:c.require(old==self.old_snapshots,'RETRY_OLD_TREE_CHANGED')
        self.old_snapshots=old;self.old_hashes=dict(self.retry['old_files'])
        self.attestation=dict(startup=startup,original_owner_issued=True,unused_roots=True,unused_ledger=True,
            roots=roots,ledger=ledger,old_prepared_sha256=self.retry['old_files'][self.retry['old_prepared']],old_snapshots=old)
        self.log_block=mounts[plan['directories']['reservation']['filesystem']]['block_bytes']
        self.max_events=4096;self.log_inode_limit=min(plan['budgets']['state_inodes']*3//4,4096)
        self.log_byte_limit=plan['budgets']['state_bytes']*3//4
        self.observed=dict(host=actual,mounts=mounts,retained_before=self.snapshot(),capacity_observed=self.capacity(mounts,inventory))
        # Bound every forthcoming event before it is written, including old
        # state occupancy and reserved assembly/ledger/finalization overhead.
        self.log_byte_limit=min(self.log_byte_limit,plan['budgets']['state_bytes']-self.costs['state']['bytes']-3*1024**2)
        self.log_inode_limit=min(self.log_inode_limit,plan['budgets']['state_inodes']-self.costs['state']['inodes']-64)
        c.require(self.log_byte_limit>3*c.LIMIT and self.log_inode_limit>128,'RETRY_STATE_RESERVATION')
        self.max_events=min(self.max_events,self.log_inode_limit-8)
        self.guard();return self.observed

    def verify_old_service_exit(self):
        for token in (self.old['preparation_id'],self.old_prepared['recovery_id']):
            value=self.unit_show('lhq'+token+'.service')
            c.require(value.get('LoadState') in ('loaded','not-found') and value.get('ActiveState') in ('inactive','failed')
                and value.get('MainPID')==value.get('ControlPID')=='0' and value.get('Job') in ('','0'), 'RETRY_OLD_OWNER_ACTIVE')

    def verify_old_source(self):
        launcher=self.old_handoff['template']['launcher'];source=launcher['source'];installation=launcher['assembly']['installation']
        c.require(source['commit']==installation['source_commit']==self.old['candidate']['commit']==self.old_prepared['source_commit'],
                  'RETRY_OLD_SOURCE_CHANGED')
        root=Path(self.old['candidate']['destination'])/'source'
        for name,digest in source['files'].items():
            self.guard();c.require(not Path(name).is_absolute() and '..' not in Path(name).parts,'RETRY_OLD_SOURCE_PATH')
            c.require(p.sha(p.read(root/name,4*1024**2,noatime=True))==digest,'RETRY_OLD_SOURCE_CHANGED')
        for program in installation['programs'].values():
            c.require(p.sha(p.read(program['path'],64*1024**2,noatime=True))==program['sha256'],'RETRY_OLD_PROGRAM_CHANGED')

    def verify_preserved(self):
        self.guard();self.verify_old_hashes();c.require(self.old_snapshot()==self.old_snapshots,'RETRY_OLD_TREE_CHANGED')
        c.require(self.snapshot()==self.observed['retained_before'],'RETRY_Q1_CHANGED')
        ledger=attest_ledger(self.retry['old_ledger']['path'],self.retry['old_ledger'],self.attestation['ledger']['authority_id'],self.guard)
        c.require(ledger==self.attestation['ledger'] and self.roots()==self.attestation['roots'],'RETRY_UNUSED_CHANGED')
        c.require(self.configuration_files()==self.configuration,'RETRY_CONFIGURATION_CHANGED')
        self.check_parents(start=False);self.verify_old_service_exit()
        mounts=self.mounts();inventory=p.Quota(self.plan['mounts']['quota']['source']).inventory(self.guard)
        c.require(inventory==self.observed['capacity_observed']['quota_inventory'],'RETRY_QUOTA_INVENTORY_CHANGED')
        self.capacity(mounts,inventory);return True

    def reserve(self,plan=None):
        c.require(self.candidate_checked,'RETRY_CANDIDATE_UNCHECKED');self.verify_preserved()
        path=Path(self.plan['directories']['reservation']['path']);pin=p.create_directory(path);self.reservation=path
        value=dict(schema=SCHEMA,retry=self.retry,issued_ns=self.issued_ns,deadline_ns=self.deadline,
            attestation=self.attestation,attestation_sha256=p.sha(c.encoded(self.attestation)),costs=self.costs)
        raw=c.encoded(value);p.create_file(path/'retry-intent.json',raw)
        self.log_bytes=((len(raw)+self.log_block-1)//self.log_block)*self.log_block
        return pin

    def directories(self):
        result={};a=self.plan['account']
        for role,item in self.plan['directories'].items():
            self.guard()
            if role in REUSED or role=='reservation':
                result[role]=p.identity(os.stat(item['path'],follow_symlinks=False),item['path']);continue
            self.event('directory-intent',dict(role=role,**item));uid,gid=(a['uid'],a['gid']) if item['owner']=='ordinary' else (0,0)
            result[role]=p.create_directory(item['path'],mode=item['mode'],owner=uid,gid=gid)
            c.require(result[role]['device']==self.plan['mounts'][item['filesystem']]['device'],'RETRY_DIRECTORY_MOUNT')
            self.event('directory-result',dict(role=role,**result[role]))
        return result

    def install(self):
        costs=self.measure_costs()
        c.require(costs['installation']['bytes']+64*1024**2<=self.plan['budgets']['installation_bytes']
            and costs['installation']['inodes']+4096<=self.plan['budgets']['installation_inodes'],
            'RETRY_INSTALLATION_RESERVATION')
        return super().install()

    def prepare(self):
        c.require(self.reservation is not None,'RETRY_RESERVATION_REQUIRED');facts=dict(self.observed)
        for name,operation in (('ordinary',self.account),('directories',self.directories),('installation',self.install),
            ('roots',self.roots),('parents',lambda:self.check_parents(start=True))):
            self.guard();self.event('step-intent',dict(step=name));facts[name]=operation();self.event('step-result',dict(step=name))
            self.measure_costs()
        self.verify_preserved();facts['retained_after']=self.snapshot()
        result=dict(schema=SCHEMA,status='RETRY_RESOURCES_PREPARED',attempt_id=self.retry['attempt_id'],
            retry_sha256=p.sha(c.encoded(self.retry)),plan_sha256=p.sha(c.encoded(self.plan)),facts=facts,
            retry=dict(directory=p.identity(self.reservation.stat(),str(self.reservation)),attestation=self.attestation,
                attestation_sha256=p.sha(c.encoded(self.attestation)),original_files_preserved=True),
            q2_accepted=False,q3_accepted=False,production_supported=False,fixture_generated=False)
        p.create_file(self.reservation/'retry-preparation.json',c.encoded(result));return result


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(dict(schema=SCHEMA,status='BLOCKED',reason='EXPLICIT_PRIVATE_INPUTS_REQUIRED',
                          q2_accepted=False,q3_accepted=False,production_supported=False)))
    return 3


if __name__=='__main__':raise SystemExit(main())
