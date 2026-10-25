"""Persistent, bounded preparation service for the existing task executor.

The ordinary adapter supplies only a task UUID and an admitted principal. It
cannot select paths, programs, quota projects, installation or resource limits.
Preparation and execution have separate durable records; reads start neither.
"""
from __future__ import annotations

import argparse
from contextlib import closing, nullcontext
import copy
import fcntl
import hashlib
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

from local_hand_jobs import budget, cli, forwarded_bounds, maintenance, quota_contract as q
from local_hand_jobs.contract import DISABLED_JOB_KINDS, JobError, Principal, MAX_WORKSPACE_TEXT_BYTES, canonical_bytes, strict_loads, validate_tool_args
from local_hand_jobs.task_session import read_descriptor
from admin.local_hand_quota_observer.protected_inputs import read_protected
from . import provision_task, task_service
from .prepared_service import FixedLauncher, unit_closed


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


def check_local_a2_management_paths(config):
    """Keep resident bookkeeping outside every registered read-only runtime.

    This runs before startup publication/locking and before a new preparation's
    private attempt files. Provisioning separately checks its generated roots.
    """
    local=config.get('local_a2')
    if local is None:
        return
    q.require(type(local) is dict and type(local.get('runtimes')) is dict,
              'RESIDENT_RUNTIME_CONFIGURATION')
    paths=[config[key] for key in ('private_root','catalog','socket','socket_descriptor') if key in config]
    for reference,runtime in local['runtimes'].items():
        value=dict(local_a2=dict(inputs={'runtime_ref':reference},runtimes={reference:runtime}),bases=paths)
        provision_task.check_local_a2_paths_before_allocation(value,dict(directories={},roots=[]))


class ResidentService:
    def __init__(self, config):
        check_local_a2_management_paths(config)
        self.config=copy.deepcopy(config) if config.get('maintenance') is not None else config
        config=self.config
        self.root=Path(config['private_root']);self.catalog=Path(config['catalog'])
        self.fence=threading.RLock();self.worker=None;self.launchers={}
        self.boot=budget.current_clock()['boot_id']
        self.maintenance_gate=maintenance.from_config(config)
        self.loaded_deployment=(maintenance.loaded_configuration(config,boot_id=self.boot)
                                if self.maintenance_gate is not None else None)
        self.protocol_ready=False
        self.records={}
        for path in sorted(self.root.glob('*/current.json')):
            record=load(path)
            operation=record['operation_id']
            validate_tool_args('lh_job_status',dict(operation_id=operation))
            q.require(path.parent.name==operation, 'RESIDENT_TASK_IDENTITY')
            self.records[operation]=record
        # The private record is authoritative. Publication may have been
        # interrupted after its commit but before replacing this derived view.
        for record in self.records.values():
            self._catalog(record)

    def recover_undispatched(self):
        """Called only after acquiring the exclusive original service lock.

        Covers death between accepting duty and publishing the task's pointer.
        ACCEPTED proves the gate's durable dispatch barrier was never crossed;
        DISPATCHING requires original exit/unit proof and is never guessed away.
        """
        if self.maintenance_gate is None:return
        for duty in self.maintenance_gate.active():
            if (duty['kind']=='prepare' and duty['state']=='ACCEPTED'
                    and duty['binding'].get('private_root')==str(self.root)):
                self.maintenance_gate.finish(duty,dict(never_dispatched=True))
                record=self.records.get(duty['operation_id'])
                if record is not None and record['attempt']==duty['attempt_id'] and record['state']=='PREPARING':
                    self._save(dict(record,state='FAILED'))

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
        return self._observe_unit_active(unit)

    def _observe_unit_active(self, unit):
        result=subprocess.run([self.config['installation']['installed']['programs']['systemctl']['path'],
            'show',unit,'-p','ActiveState','--value'],capture_output=True,text=True,timeout=3)
        state=result.stdout.strip()
        active={'active','activating','deactivating','reloading'}
        if result.returncode!=0 or state not in active|{'inactive','failed'}:
            raise JobError('IO_UNCERTAIN','Cannot observe the original system unit')
        return state in active

    def _launcher(self, record):
        key=record['attempt']
        if key not in self.launchers:
            launch=load(record['launch_path'])
            bounds={}
            if self.maintenance_gate is not None:
                prepared=record.get('maintenance_prepared')
                if prepared is not None and (prepared.get('operation_id')!=record['operation_id']
                        or prepared.get('attempt_id')!=record['attempt']
                        or prepared.get('request_digest')!=launch['request']['request_digest']
                        or prepared.get('resource_digest')!=maintenance.digest(launch)):
                    raise JobError('STALE_DEPLOYMENT','Original preparation has no matching deployment binding')
                bounds=dict(maintenance_gate=self.maintenance_gate,loaded=self.loaded_deployment,prepared=prepared)
            self.launchers[key]=FixedLauncher(launch,self.config['installation'],
                record['launch_path'],record['output'],**bounds)
        return self.launchers[key]

    def execution_state(self, record):
        output=Path(record['output'])
        if (output/'finished.json').exists():
            launcher=self.launchers.get(record.get('attempt'))
            if launcher is not None and launcher.complete.is_set():
                # The name can exist before its directory sync succeeds.
                # Let the original collector verify/persist its own result.
                launcher.state()
            return self._captured_execution_state(record)
        intent=(output/'launch-intent.json').exists() or (output/'started.json').exists()
        if record['boot_id']!=self.boot:
            return 'UNRESOLVED' if intent else 'IDLE'
        launcher=self._launcher(record)
        try:state=launcher.state()
        except JobError as error:
            if error.code!='IO_UNCERTAIN':raise
            # A daemon restart loses the pipe collector, not the original task.
            # Reattach only its API for queries/submission deduplication. Never
            # issue another controller start for a retained launch intent.
            return 'RUNNING' if self._unit_active(record) else 'UNRESOLVED'
        return self._captured_execution_state(record) if state=='EXITED' else state

    def _captured_execution_state(self, record):
        proof=load(Path(record['output'])/'finished.json')
        q.require(type(proof.get('returncode')) is int and proof.get('streams_eof') is True,'RESIDENT_EXIT_PROOF')
        # Nonzero waiter exit plus EOF does not prove that its systemd unit
        # stopped. Keep routing to a live controller and fence new work until
        # it has stopped; an observation failure remains retryable uncertainty.
        if proof['returncode']!=0 and record['boot_id']==self.boot and self._unit_active(record):
            return 'RUNNING'
        return 'EXITED'

    def _has_committed_task(self, record):
        policy=load(record['launch_path'])['policy']
        path=Path(policy['broker_root'])/'jobs.sqlite'
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            return db.execute("select 1 from operations where namespace='job' and id=?",
                              (record['operation_id'],)).fetchone() is not None

    def _replaceable(self, record, *, failed_only=False):
        output=Path(record['output'])
        if not (output/'launch-intent.json').exists() and not (output/'started.json').exists():
            # A retry poll after successful preparation must keep the exact
            # READY request. Unsubmitted tasks are replaced only when stale.
            return not failed_only
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
            attempt=Path(record['attempt'])
            if record['state']!='READY' and (attempt/'preparation-delivery.json').exists():
                # A failed/killed systemd-run waiter may leave its service
                # running. Only a successful --wait exit proves completion;
                # otherwise observe the original unit before admitting work.
                exit_path=attempt/'preparation-exit.json'
                code=load(exit_path).get('returncode') if exit_path.exists() else None
                if not (type(code) is int and code==0) and self._preparation_active(record):
                    return True
        return any(record['state']=='READY' and operation!=except_operation
                   and self.execution_state(record)=='RUNNING' for operation,record in self.records.items())

    def _preparation_active(self, record):
        return self._observe_unit_active(record['prepare_unit'])

    def prepare(self, args, principal, *, allow_new=True, authorization=None):
        check_local_a2_management_paths(self.config)
        operation=args['operation_id']
        if args['profile_ref']!=self.config['profile_ref']:
            raise JobError('UNAUTHORIZED','Preparation profile differs')
        if args['kind']=='workspace.edit':
            workspace=self.config.get('workspace',{})
            source=workspace.get('sources',{}).get(args['inputs']['source_ref'])
            if (source is None or args['inputs']['validation_ref'] not in source.get('validations',{})
                    or args['inputs']['relative_path'] not in source['blobs']):
                raise JobError('UNAUTHORIZED','Workspace source, file or validation is not admitted')
        # Old runtime registration cannot reactivate a retired temporary job.
        # Existing immutable preparations remain queryable with original inputs.
        allow_new = allow_new and args['kind'] not in DISABLED_JOB_KINDS
        with self.fence:
            record=self.records.get(operation)
            if record is not None:
                self._owned(operation,principal)
                selected=record.get('request',record)
                if (selected.get('kind','host.inspect')!=args['kind']
                        or selected.get('inputs',{})!=args.get('inputs',{})):
                    raise JobError('CONFLICT','Prepared task input changed; keep its original identity')
                if record['state']=='PREPARING':
                    if self.worker is not None and self.worker.is_alive():
                        return dict(operation_id=operation,state='PREPARING')
                    # After restart, recover a completed preparation or retain
                    # its failure. Neither path submits any business operation.
                    if self._preparation_active(record):return dict(operation_id=operation,state='PREPARING')
                    if (Path(record['attempt'])/'result.json').exists():
                        try:record=self._ready(record)
                        except Exception as error:record=self._preparation_failed(record,error)
                    else:
                        record=dict(record,state='FAILED');self._save(record)
                if record['state']=='READY':
                    if not allow_new:
                        self._catalog(record)
                        return dict(operation_id=operation,state='READY',request=record['request'])
                    stale=record['boot_id']!=self.boot or record['request']['expires_at']<=time.time()
                    if self.maintenance_gate is not None:
                        bound=record.get('maintenance_prepared',{})
                        stale=stale or any(bound.get(key)!=self.loaded_deployment[key] for key in
                                          ('deployment_digest','configuration_digest','payload_digest'))
                    if (args.get('retry_failed') and self.config.get('installation',{}).get('source')
                            and record.get('launch_path')):
                        original=load(record['launch_path'])['policy']
                        # A local admission failure before execution may use
                        # the repaired installation under the same UUID. Keep
                        # completed or possibly delivered work on its version.
                        stale = stale or (original['source_commit']!=self.config['installation']['source']['commit']
                                          and not self._has_committed_task(record))
                    if not (stale or args.get('retry_failed')) or not self._replaceable(record,failed_only=not stale):
                        self._catalog(record)
                        return dict(operation_id=operation,state='READY',request=record['request'])
                if record['state']=='FAILED' and (not args.get('retry_failed') or not allow_new):
                    return dict(operation_id=operation,state='FAILED',retryable=allow_new)
            if not allow_new:
                raise JobError('UNSUPPORTED','This job is not available for new preparation')
            if self._busy():raise JobError('RESOURCE_BUSY','Another task is preparing or running')
            if record is None and len(self.records)>=self.config['max_tasks']:
                raise JobError('LIMIT_EXCEEDED','Retained task capacity is full')
            operation_root=self.root/operation
            used=[int(p.name.split('-')[-1]) for p in self.root.glob('*/attempt-*') if p.is_dir()]
            serial=max(used,default=0)+1
            if self.config['first_project_id']+serial*7-1>self.config['last_project_id']:
                raise JobError('LIMIT_EXCEEDED','Configured quota project range is full')
            if authorization is not None:
                authorization.require_current()
            attempt=operation_root/('attempt-'+str(serial))
            record=dict(operation_id=operation,principal_id=principal,state='PREPARING',attempt=str(attempt),
                serial=serial,boot_id=self.boot,prepare_unit='lhprepare'+uuid.UUID(operation).hex+'a'+str(serial)+'.service')
            if args['kind'] in {'workspace.edit','ledger.test.local_a2'}:
                record.update(kind=args['kind'],inputs=args['inputs'])
            receipt=None
            if self.maintenance_gate is not None:
                receipt=self.maintenance_gate.accept('prepare',operation,str(attempt),
                    dict(arguments=args,principal_id=principal,private_root=str(self.root)),
                    self.loaded_deployment,authorization=authorization)
                record['maintenance_admission']=receipt
            ready=threading.Event()
            started=False
            def work_after_start():
                ready.wait()
                if started:self._prepare_worker(*worker_args)
            try:
                operation_root.mkdir(mode=0o700,exist_ok=True)
                attempt.mkdir(mode=0o700)
                self._save(record)
                worker_args=(record,) if authorization is None else (record,authorization)
                self.worker=threading.Thread(target=work_after_start,daemon=True)
                self.worker.start()
                started=True
            except BaseException:
                # Even if native thread creation happened, it cannot dispatch
                # until successful start() acknowledgement sets started.
                if receipt is not None and not started:
                    self.maintenance_gate.finish(receipt,dict(never_dispatched=True))
                raise
            finally:
                ready.set()
            return dict(operation_id=operation,state='PREPARING')

    def _ready(self, record):
        prepared=load(Path(record['attempt'])/'result.json')
        launch=prepared['launch'];request=launch['request']
        q.require(request['operation_id']==record['operation_id'] and launch['principal_id']==record['principal_id'],
                  'RESIDENT_PREPARED_IDENTITY')
        q.require(request['kind']==record.get('kind','host.inspect')
                  and request['inputs']==record.get('inputs',{}),'RESIDENT_PREPARED_INPUTS')
        admission=task_service.TaskService(launch)
        admission.close()
        output=Path(record['attempt'])/'execution'
        output.mkdir(mode=0o700,exist_ok=True)
        record=dict(record,state='READY',request=request,policy_path=launch['policy_path'],
            launch_path=str(Path(prepared['reservation'])/'launch-static.json'),output=str(output),
            controller_unit=launch['controller_envelope']['controller']['unit'])
        if self.maintenance_gate is not None:
            original=record.get('maintenance_admission')
            if original is None:
                raise JobError('STALE_DEPLOYMENT','Preparation did not enter the shared maintenance barrier')
            record['maintenance_prepared']=maintenance.prepared_binding(original['loaded'],
                operation_id=record['operation_id'],attempt_id=record['attempt'],
                request_digest=request['request_digest'],launch=launch)
        self._save(record)
        return record

    def _prepare_worker(self, record, authorization=None):
        attempt=Path(record['attempt'])
        receipt=record.get('maintenance_admission')
        delivered=False
        closed=False
        try:
            extra={'workspace_inputs':record['inputs']} if record.get('kind')=='workspace.edit' else {}
            if record.get('kind')=='ledger.test.local_a2':
                extra={'local_a2_inputs':record['inputs']}
            value=provision_task.task_input(self.config,record['operation_id'],record['principal_id'],record['serial'],**extra)
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
            if authorization is not None:authorization.require_current()
            if receipt is not None:
                self.maintenance_gate.dispatch(receipt,authorization=authorization)
            delivered=True
            result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,timeout=78,
                                  env={'PATH':'/usr/bin:/bin'},cwd='/')
            publish(attempt/'preparation-exit.json',dict(returncode=result.returncode,
                stdout=result.stdout[:32768].hex(),stderr=result.stderr[:32768].hex(),
                stdout_bytes=len(result.stdout),stderr_bytes=len(result.stderr)))
            if result.returncode!=0:raise ValueError('PROVISION_PROCESS_FAILED')
            closed=True
            with self.fence:self._ready(record)
        except BaseException as error:
            with self.fence:self._preparation_failed(record,error)
        finally:
            if receipt is not None:
                try:
                    if not delivered:
                        self.maintenance_gate.finish(receipt,dict(never_dispatched=True))
                    elif closed or unit_closed(self.config['installation']['installed']['programs']['systemctl']['path'],
                                                record['prepare_unit']):
                        self.maintenance_gate.finish(receipt,dict(process_exited=True,writers_stopped=True))
                except (JobError,OSError,ValueError,subprocess.SubprocessError):
                    pass # Unobserved closure remains visible to deployment.

    def deployment_observe(self):
        """Strictly read-only proof for planning; no responsibility reconciliation."""
        if self.maintenance_gate is None:
            return dict(maintenance_supported=False)
        marker=self.maintenance_gate.snapshot()
        return dict(maintenance_supported=True,loaded=maintenance.process_proof(
                        self.loaded_deployment,protocol_ready=self.protocol_ready),
                    marker={key:marker[key] for key in ('state','sequence','owner','decision_id','deployment_digest')})

    def deployment_status(self):
        """Explicit drain observation may close only positively proved duties."""
        if self.maintenance_gate is None:
            return dict(maintenance_supported=False)
        # A crashed collector is not silently forgotten. Reuse retained exit
        # proof and positively observe the original unit before closing duty.
        for record in self.records.values():
            receipt=record.get('maintenance_admission')
            if receipt is not None:
                try:
                    attempt=Path(record['attempt'])
                    active={item['id']:item for item in self.maintenance_gate.active()}
                    duty=active.get(receipt['id'])
                    if duty is not None and not (self.worker is not None and self.worker.is_alive()):
                        if duty['state']=='ACCEPTED' and not (attempt/'preparation-delivery.json').exists():
                            self.maintenance_gate.finish(receipt,dict(never_dispatched=True))
                        elif (attempt/'preparation-exit.json').exists() and unit_closed(
                                self.config['installation']['installed']['programs']['systemctl']['path'],record['prepare_unit']):
                            self.maintenance_gate.finish(receipt,dict(process_exited=True,writers_stopped=True))
                    if record['state']=='READY':
                        self._launcher(record).state()
                except (JobError,OSError,ValueError,subprocess.SubprocessError):
                    pass
        return self.deployment_observe()

    def _preparation_failed(self, record, error):
        directory=os.open(record['attempt'],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        failure=dict(type=type(error).__name__,message=str(error)[:2048])
        try:
            try:task_service.save(directory,'preparation-failure.json',failure)
            except FileExistsError:
                task_service.save(directory,'preparation-failure-'+uuid.uuid4().hex+'.json',failure)
        finally:os.close(directory)
        current=self.records[record['operation_id']]
        # A publication error after the private READY commit must not demote a
        # successful preparation. A later poll/restart repairs its public view.
        if current['state']=='READY' and current['attempt']==record['attempt']:
            return current
        failed=dict(record,state='FAILED')
        self._save(failed)
        return failed

    def call(self, request):
        with self.fence:
            action=request.get('action');principal=request.get('principal_id')
            if principal not in self.config['principals']:
                raise JobError('UNAUTHORIZED','Principal is not admitted')
            authorization=None
            if 'authorization_bounds' in request:
                # serve() has already authenticated the fixed adapter UID.
                # Its registered principal and installed task grant remain
                # the upper bound; JSON cannot introduce a new principal.
                scopes=self.config.get('template',{}).get('scopes')
                if type(scopes) is not list:
                    raise JobError('UNAUTHORIZED','Installed scope grant is unavailable')
                request,authorization=forwarded_bounds.restrict(request,Principal(principal,frozenset(scopes)))
                required={'prepare':{'lh:submit'},'start':{'lh:submit'},'workspace_read':{'lh:read'},
                          'status':{'lh:read','lh:submit','lh:cancel','lh:evidence'},
                          'deployment_status':{'lh:inspect'},'deployment_observe':{'lh:inspect'}}.get(action,set())
                if not required.intersection(authorization.scopes):
                    raise JobError('UNAUTHORIZED','Forwarded scope does not permit this action')
            if action in {'deployment_status','deployment_observe'}:
                q.require(set(request)=={'action','principal_id'},'RESIDENT_REQUEST')
                if authorization is not None:authorization.require_current()
                return self.deployment_status() if action=='deployment_status' else self.deployment_observe()
            if action=='workspace_read':
                q.require(set(request)=={'action','principal_id','profile_ref','source_ref','relative_path'},'RESIDENT_REQUEST')
                args=validate_tool_args('lh_workspace_read',{k:v for k,v in request.items() if k not in {'action','principal_id'}})
                source=self.config.get('workspace',{}).get('sources',{}).get(args['source_ref'])
                if (args['profile_ref']!=self.config['profile_ref'] or source is None
                        or args['relative_path'] not in source['blobs']):
                    raise JobError('UNAUTHORIZED','Workspace source or file is not admitted')
                if authorization is not None:authorization.require_current()
                try:raw=read_protected(str(Path(source['root'])/args['relative_path']),MAX_WORKSPACE_TEXT_BYTES)
                except ValueError as error:
                    if str(error)=='INPUT_BYTE_LIMIT':
                        raise JobError('LIMIT_EXCEEDED','Workspace file exceeds 120 KiB of UTF-8 text') from None
                    raise
                if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=source['blobs'][args['relative_path']]:
                    raise JobError('CONFLICT','Workspace source file changed')
                try:content=raw.decode('utf-8',errors='strict')
                except UnicodeError:raise JobError('UNSUPPORTED','Workspace file is not UTF-8 text') from None
                result=dict(source_ref=args['source_ref'],source_commit=source['commit'],relative_path=args['relative_path'],
                            sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),content=content)
                if len(canonical_bytes(dict(result=result)))>cli.MAX_RESPONSE_BYTES:
                    raise JobError('LIMIT_EXCEEDED','Workspace text exceeds the 512 KiB response budget after JSON escaping')
                return result
            if action=='prepare':
                q.require({'action','principal_id','operation_id','kind','profile_ref'}<=set(request)
                          <={'action','principal_id','operation_id','kind','profile_ref','retry_failed','inputs','allow_new'},'RESIDENT_REQUEST')
                allow_new=request.get('allow_new',True)
                q.require(type(allow_new) is bool,'RESIDENT_REQUEST')
                args=validate_tool_args('lh_job_prepare',{k:v for k,v in request.items() if k not in {'action','principal_id','allow_new'}})
                bounds={} if authorization is None else {'authorization':authorization}
                return self.prepare(args,principal,allow_new=allow_new,**bounds)
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
                    if record['request']['kind'] in DISABLED_JOB_KINDS:
                        raise JobError('UNSUPPORTED','This job kind is not available for new execution')
                    if record['boot_id']!=self.boot or record['request']['expires_at']<=time.time():
                        raise JobError('STALE_DEPLOYMENT','Prepare the unsubmitted task for this boot')
                    if self._busy(except_operation=operation):
                        raise JobError('RESOURCE_BUSY','Another task is active')
                    if authorization is not None:authorization.require_current()
                    bounds={} if authorization is None else {'authorization':authorization}
                    state=self._launcher(record).start(**bounds)
                    if state=='EXITED':state=self._captured_execution_state(record)
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
    check_local_a2_management_paths(config)
    for key in ('private_root','catalog'):
        path=Path(config[key])
        for item in (path,*path.parents):
            info=item.lstat()
            q.require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'RESIDENT_DIRECTORY')
    lock=os.open(Path(config['private_root'])/'service.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    service=ResidentService(config)
    service.recover_undispatched()
    if service.maintenance_gate is not None:
        from local_hand_jobs.deployment import verify_release
        from local_hand_jobs import startup
        installation=config['installation']
        verify_release(expected_source_commit=installation['source']['commit'],
            expected_payload_digest=installation['installed']['payload_digest'],
            expected_entrypoint=installation['installed']['package_root']+'/local_hand_jobs/cli.py',
            actual_entrypoint=cli.__file__)
    endpoint=Path(config['socket']);parent=endpoint.parent
    for item in (parent,*parent.parents):
        info=item.lstat()
        q.require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'RESIDENT_SOCKET_PARENT')
    if endpoint.exists():
        info=endpoint.lstat()
        q.require(stat.S_ISSOCK(info.st_mode) and info.st_uid==0,'RESIDENT_SOCKET_CHANGED')
        endpoint.unlink() # The service lock excludes another admitted listener.
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
        guard=(startup.authorize(config,service.loaded_deployment,service.maintenance_gate)
               if service.maintenance_gate is not None else nullcontext())
        with guard:
            listener.bind(str(endpoint));os.chown(endpoint,0,config['gid']);endpoint.chmod(0o660);listener.listen(16)
            service.protocol_ready=True
        info=endpoint.lstat()
        publish(config['socket_descriptor'],dict(socket=dict(path=str(endpoint),device=info.st_dev,inode=info.st_ino)),0o644)
        while True:
            connection,_=listener.accept()
            with connection:
                end=time.monotonic()+3
                try:
                    peer_pid,uid,gid=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    request=strict_loads(cli._read_frame(connection,cli.MAX_REQUEST_BYTES,deadline=end))
                    if (request=={'action':'startup_authorize','component':'mcp'}
                            and (uid==0 or (uid,gid)==(config['uid'],config['gid']))):
                        if service.maintenance_gate is None:
                            raise JobError('UNSUPPORTED','Legacy service has no startup selection authority')
                        startup.serve_authorization(connection,config,service.maintenance_gate,peer_pid=peer_pid)
                        continue
                    if uid==0 and request in ({'action':'startup_authorize','component':'gateway','mode':'candidate'},
                                               {'action':'startup_authorize','component':'gateway','mode':'public'}):
                        if service.maintenance_gate is None:
                            raise JobError('UNSUPPORTED','Legacy service has no gateway startup authority')
                        startup.serve_gateway_authorization(connection,config,service.maintenance_gate,
                            peer_pid=peer_pid,peer_uid=uid,mode=request['mode'])
                        continue
                    if uid==0 and request in ({'action':'deployment_status'},{'action':'deployment_observe'}):
                        with service.fence:
                            result=(service.deployment_status() if request['action']=='deployment_status'
                                    else service.deployment_observe())
                    else:
                        if (uid,gid)!=(config['uid'],config['gid']):raise JobError('UNAUTHORIZED','Peer is not admitted')
                        result=service.call(request)
                    response=dict(result=result)
                except JobError as error:response=dict(error=error.as_dict())
                except Exception:response=dict(error=dict(code='IO_UNCERTAIN',message='Task service needs state inspection'))
                try:cli._send_frame(connection,response,deadline=end,limit=cli.MAX_RESPONSE_BYTES)
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
