"""Persistent, bounded preparation service for the existing task executor.

The ordinary adapter supplies only a task UUID and an admitted principal. It
cannot select paths, programs, quota projects, installation or resource limits.
Preparation and execution have separate durable records; reads start neither.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import socket
import sqlite3
import stat
import struct
import subprocess
import threading
import time
import uuid

from local_hand_jobs import budget, cli, quota_contract as q
from local_hand_jobs.contract import JobError, strict_loads, validate_tool_args
from local_hand_jobs.task_session import read_descriptor
from admin.local_hand_quota_observer.protected_inputs import read_protected
from . import provision_task, task_service
from .prepared_service import FixedLauncher


def load(path):
    return q._load(read_protected(str(path), 2*1024**2), 2*1024**2, 32)


def publish(path, value, mode=0o600):
    """Replace only this service's current pointer; attempt records stay intact."""
    path=Path(path)
    directory=os.open(path.parent, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    name='.'+path.name+'-'+uuid.uuid4().hex
    try:
        task_service.save(directory, name, value, mode)
        os.rename(name, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:os.close(directory)


class ResidentService:
    def __init__(self, config):
        self.config=config
        self.root=Path(config['private_root']);self.catalog=Path(config['catalog'])
        self.fence=threading.RLock();self.worker=None;self.launchers={}
        self.boot=budget.current_clock()['boot_id']
        self.records={}
        for path in sorted(self.root.glob('*/current.json')):
            record=load(path)
            operation=record['operation_id']
            validate_tool_args('lh_job_status',dict(operation_id=operation))
            q.require(path.parent.name==operation, 'RESIDENT_TASK_IDENTITY')
            self.records[operation]=record

    def _catalog(self, record):
        public={k:record[k] for k in ('operation_id','principal_id','state')}
        if record['state']=='READY':
            public.update(request=record['request'],policy_path=record['policy_path'])
        publish(self.catalog/(record['operation_id']+'.json'),public,0o644)

    def _save(self, record):
        publish(self.root/record['operation_id']/'current.json',record)
        self.records[record['operation_id']]=record
        self._catalog(record)

    def _owned(self, operation, principal):
        record=self.records.get(operation)
        if record is None:raise JobError('NOT_FOUND','Task is not prepared')
        if record['principal_id']!=principal:raise JobError('UNAUTHORIZED','Task owner differs')
        return record

    def _unit_active(self, record):
        unit=record.get('controller_unit')
        if not unit:return False
        result=subprocess.run([self.config['installation']['installed']['programs']['systemctl']['path'],
            'show',unit,'-p','ActiveState','--value'],capture_output=True,text=True,timeout=3)
        if result.returncode!=0:raise JobError('IO_UNCERTAIN','Cannot observe the original controller')
        return result.stdout.strip() in {'active','activating','deactivating','reloading'}

    def _launcher(self, record):
        key=record['attempt']
        if key not in self.launchers:
            launch=load(record['launch_path'])
            self.launchers[key]=FixedLauncher(launch,self.config['installation'],
                record['launch_path'],record['output'])
        return self.launchers[key]

    def execution_state(self, record):
        output=Path(record['output'])
        if (output/'finished.json').exists():
            proof=load(output/'finished.json')
            q.require(type(proof.get('returncode')) is int and proof.get('streams_eof') is True,'RESIDENT_EXIT_PROOF')
            return 'EXITED'
        intent=(output/'launch-intent.json').exists() or (output/'started.json').exists()
        if record['boot_id']!=self.boot:
            return 'UNRESOLVED' if intent else 'IDLE'
        launcher=self._launcher(record)
        try:return launcher.state()
        except JobError as error:
            if error.code!='IO_UNCERTAIN':raise
            # A daemon restart loses the pipe collector, not the original task.
            # Reattach only its API for queries/submission deduplication. Never
            # issue another controller start for a retained launch intent.
            return 'RUNNING' if self._unit_active(record) else 'UNRESOLVED'

    def _has_committed_task(self, record):
        policy=load(record['launch_path'])['policy']
        path=Path(policy['broker_root'])/'jobs.sqlite'
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            return db.execute("select 1 from operations where namespace='job' and id=?",
                              (record['operation_id'],)).fetchone() is not None

    def _replaceable(self, record):
        output=Path(record['output'])
        if not (output/'launch-intent.json').exists() and not (output/'started.json').exists():return True
        # A proved pre-admission failure may be prepared again. A committed job,
        # missing exit capture or unknown write is never replaced.
        finished=output/'finished.json'
        if not finished.exists():return False
        proof=load(finished)
        return (type(proof.get('returncode')) is int and proof.get('streams_eof') is True
                and not self._unit_active(record) and not self._has_committed_task(record))

    def _busy(self, except_operation=None):
        if self.worker is not None and self.worker.is_alive():return True
        for record in self.records.values():
            if (record['state']!='READY' and (Path(record['attempt'])/'preparation-delivery.json').exists()
                    and not (Path(record['attempt'])/'preparation-exit.json').exists()
                    and self._preparation_active(record)):
                return True
        return any(record['state']=='READY' and operation!=except_operation
                   and self.execution_state(record)=='RUNNING' for operation,record in self.records.items())

    def _preparation_active(self, record):
        result=subprocess.run([self.config['installation']['installed']['programs']['systemctl']['path'],
            'show',record['prepare_unit'],'-p','ActiveState','--value'],capture_output=True,text=True,timeout=3)
        if result.returncode!=0:raise JobError('IO_UNCERTAIN','Cannot observe preparation')
        return result.stdout.strip() in {'active','activating','deactivating','reloading'}

    def prepare(self, args, principal):
        operation=args['operation_id']
        if args['profile_ref']!=self.config['profile_ref']:
            raise JobError('UNAUTHORIZED','Preparation profile differs')
        with self.fence:
            record=self.records.get(operation)
            if record is not None:
                self._owned(operation,principal)
                if record['state']=='PREPARING':
                    if self.worker is not None and self.worker.is_alive():
                        return dict(operation_id=operation,state='PREPARING')
                    # After restart, recover a completed preparation or retain
                    # its failure. Neither path submits any business operation.
                    if self._preparation_active(record):return dict(operation_id=operation,state='PREPARING')
                    if (Path(record['attempt'])/'result.json').exists():
                        record=self._ready(record)
                    else:
                        record=dict(record,state='FAILED');self._save(record)
                if record['state']=='READY':
                    stale=record['boot_id']!=self.boot or record['request']['expires_at']<=time.time()
                    if not (stale or args.get('retry_failed')) or not self._replaceable(record):
                        return dict(operation_id=operation,state='READY',request=record['request'])
                if record['state']=='FAILED' and not args.get('retry_failed'):
                    return dict(operation_id=operation,state='FAILED',retryable=True)
            if self._busy():raise JobError('RESOURCE_BUSY','Another task is preparing or running')
            if record is None and len(self.records)>=self.config['max_tasks']:
                raise JobError('LIMIT_EXCEEDED','Retained task capacity is full')
            operation_root=self.root/operation
            operation_root.mkdir(mode=0o700,exist_ok=True)
            used=[int(p.name.split('-')[-1]) for p in self.root.glob('*/attempt-*') if p.is_dir()]
            serial=max(used,default=0)+1
            if self.config['first_project_id']+serial*7>self.config['last_project_id']:
                raise JobError('LIMIT_EXCEEDED','Configured quota project range is full')
            attempt=operation_root/('attempt-'+str(serial))
            attempt.mkdir(mode=0o700)
            record=dict(operation_id=operation,principal_id=principal,state='PREPARING',attempt=str(attempt),
                serial=serial,boot_id=self.boot,prepare_unit='lhprepare'+uuid.UUID(operation).hex+'a'+str(serial)+'.service')
            self._save(record)
            self.worker=threading.Thread(target=self._prepare_worker,args=(record,),daemon=True)
            self.worker.start()
            return dict(operation_id=operation,state='PREPARING')

    def _ready(self, record):
        prepared=load(Path(record['attempt'])/'result.json')
        launch=prepared['launch'];request=launch['request']
        q.require(request['operation_id']==record['operation_id'] and launch['principal_id']==record['principal_id'],
                  'RESIDENT_PREPARED_IDENTITY')
        admission=task_service.TaskService(launch)
        admission.close()
        output=Path(record['attempt'])/'execution'
        output.mkdir(mode=0o700,exist_ok=True)
        record=dict(record,state='READY',request=request,policy_path=launch['policy_path'],
            launch_path=str(Path(prepared['reservation'])/'launch-static.json'),output=str(output),
            controller_unit=launch['controller_envelope']['controller']['unit'])
        self._save(record)
        return record

    def _prepare_worker(self, record):
        attempt=Path(record['attempt'])
        try:
            value=provision_task.task_input(self.config,record['operation_id'],record['principal_id'],record['serial'])
            publish(attempt/'input.json',value)
            installation=self.config['installation'];programs=installation['installed']['programs']
            command=[programs['systemd_run']['path'],'--quiet','--wait','--pipe','--unit='+record['prepare_unit'],
                '--property=Type=exec','--property=RuntimeMaxSec=70s','--property=TimeoutStopSec=2s',
                '--property=KillMode=control-group','--property=MemoryMax=256M','--property=TasksMax=32',
                '--property=CPUQuota=100%','--property=NoNewPrivileges=yes','--property=UMask=0077','--',
                programs['python']['path'],'-I','-B','-c',
                'import sys;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];'
                'from admin.local_hand_system_manager.resident_service import prepare_main;prepare_main(*sys.argv[1:])',
                installation['installed']['package_root'],installation['source']['root']+'/tools',
                str(attempt/'input.json'),str(attempt/'result.json')]
            publish(attempt/'preparation-delivery.json',dict(command=command))
            result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,timeout=78,
                                  env={'PATH':'/usr/bin:/bin'},cwd='/')
            publish(attempt/'preparation-exit.json',dict(returncode=result.returncode,
                stdout=result.stdout[:32768].hex(),stderr=result.stderr[:32768].hex(),
                stdout_bytes=len(result.stdout),stderr_bytes=len(result.stderr)))
            if result.returncode!=0:raise ValueError('PROVISION_PROCESS_FAILED')
            with self.fence:self._ready(record)
        except BaseException as error:
            publish(attempt/'preparation-failure.json',dict(type=type(error).__name__,message=str(error)[:2048]))
            with self.fence:self._save(dict(record,state='FAILED'))

    def call(self, request):
        with self.fence:
            action=request.get('action');principal=request.get('principal_id')
            if principal not in self.config['principals']:
                raise JobError('UNAUTHORIZED','Principal is not admitted')
            if action=='prepare':
                q.require({'action','principal_id','operation_id','kind','profile_ref'}<=set(request)
                          <={'action','principal_id','operation_id','kind','profile_ref','retry_failed'},'RESIDENT_REQUEST')
                args=validate_tool_args('lh_job_prepare',{k:v for k,v in request.items() if k not in {'action','principal_id'}})
                return self.prepare(args,principal)
            if action not in {'status','start'}:raise JobError('UNSUPPORTED','Unknown task service action')
            q.require(set(request)=={'action','principal_id','operation_id'}|({'request_digest'} if action=='start' else set()),
                      'RESIDENT_REQUEST')
            operation=validate_tool_args('lh_job_status',dict(operation_id=request['operation_id']))['operation_id']
            record=self._owned(operation,principal)
            if record['state']!='READY':raise JobError('RESOURCE_BUSY','Preparation is not ready')
            state=self.execution_state(record)
            if action=='start':
                if request['request_digest']!=record['request']['request_digest']:
                    raise JobError('CONFLICT','Task request changed')
                if state=='IDLE':
                    if record['boot_id']!=self.boot or record['request']['expires_at']<=time.time():
                        raise JobError('STALE_DEPLOYMENT','Prepare the unsubmitted task for this boot')
                    if self._busy(except_operation=operation):
                        raise JobError('RESOURCE_BUSY','Another task is active')
                    state=self._launcher(record).start()
            return dict(state=state)


def prepare_main(input_path,result_path):
    value=provision_task.prepare(load(input_path))
    directory=os.open(str(Path(result_path).parent),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:task_service.save(directory,Path(result_path).name,value)
    finally:os.close(directory)


def initialize_host(config):
    """Start the original execution slices; new tasks bind their current pins."""
    q.require(os.getuid()==os.geteuid()==0,'RESIDENT_ADMINISTRATOR')
    template=config['template'];uid,gid=config['uid'],config['gid']
    systemctl=config['installation']['installed']['programs']['systemctl']['path']
    units=sorted({Path(value['path']).name for value in template['observed']['parents'].values()})
    def run(argv,env=None):
        result=subprocess.run(argv,capture_output=True,timeout=15,env=env)
        q.require(result.returncode==0,'RESIDENT_RUNTIME_PREPARATION')
    run([systemctl,'start',*units,'user@'+str(uid)+'.service'])
    old=template['observed']['system_geometry']['retained_ordinary_parent']
    q.require((old['memory_bytes'],old['tasks_max'],old['memory_swap_max'],old['cpu_quota_per_sec_usec'])
              ==(268435456,64,0,1000000),'RESIDENT_RETAINED_PARENT_BUDGET')
    prefix=[template['plan']['tools']['setpriv']['path'],'--reuid='+str(uid),'--regid='+str(gid),
            '--clear-groups','--no-new-privs','--',systemctl,'--user']
    env={'PATH':'/usr/bin:/bin','XDG_RUNTIME_DIR':'/run/user/'+str(uid),
         'DBUS_SESSION_BUS_ADDRESS':'unix:path=/run/user/'+str(uid)+'/bus'}
    name=Path(old['parent']['path']).name
    run(prefix+['start',name],env)
    run(prefix+['set-property','--runtime',name,'MemoryMax=268435456','MemorySwapMax=0',
                'TasksMax=64','CPUQuota=100%','CPUQuotaPeriodSec=100ms'],env)


def serve(config):
    q.require(os.getuid()==os.geteuid()==0,'RESIDENT_ADMINISTRATOR')
    for key in ('private_root','catalog'):
        path=Path(config[key])
        for item in (path,*path.parents):
            info=item.lstat()
            q.require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'RESIDENT_DIRECTORY')
    lock=os.open(Path(config['private_root'])/'service.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    service=ResidentService(config)
    endpoint=Path(config['socket']);parent=endpoint.parent
    for item in (parent,*parent.parents):
        info=item.lstat()
        q.require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'RESIDENT_SOCKET_PARENT')
    if endpoint.exists():
        info=endpoint.lstat()
        q.require(stat.S_ISSOCK(info.st_mode) and info.st_uid==0,'RESIDENT_SOCKET_CHANGED')
        endpoint.unlink() # The service lock excludes another admitted listener.
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
        listener.bind(str(endpoint));os.chown(endpoint,0,config['gid']);endpoint.chmod(0o660);listener.listen(16)
        info=endpoint.lstat()
        publish(config['socket_descriptor'],dict(socket=dict(path=str(endpoint),device=info.st_dev,inode=info.st_ino)),0o644)
        while True:
            connection,_=listener.accept()
            with connection:
                end=time.monotonic()+3
                try:
                    _,uid,gid=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    if (uid,gid)!=(config['uid'],config['gid']):raise JobError('UNAUTHORIZED','Peer is not admitted')
                    result=service.call(strict_loads(cli._read_frame(connection,8192,deadline=end)))
                    response=dict(result=result)
                except JobError as error:response=dict(error=error.as_dict())
                except Exception:response=dict(error=dict(code='IO_UNCERTAIN',message='Task service needs state inspection'))
                try:cli._send_frame(connection,response,deadline=end,limit=16384)
                except (OSError,JobError):pass


def main(argv=None):
    parser=argparse.ArgumentParser(description='Run the persistent Local Hand preparation service')
    parser.add_argument('--config',required=True)
    parser.add_argument('--initialize-host',action='store_true')
    args=parser.parse_args(argv)
    config=load(args.config)
    if args.initialize_host:initialize_host(config)
    else:serve(config)


if __name__=='__main__':main()
